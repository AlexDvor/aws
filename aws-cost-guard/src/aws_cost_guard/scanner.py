"""Continue independent checks after errors; retain per-check coverage."""
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from .aws_session import AWS, error_code, pages
from .resource_analyzer import analyze, extract
from .services.catalog import Check, GLOBAL, REGIONAL


def records(page: dict, path: str) -> list:
    values = [page]
    for part in path.split("."):
        values = [item for value in values for item in value.get(part, [])]
    return values


class Scanner:
    def __init__(self, aws: AWS):
        self.aws = aws
        self.report: dict[str, Any] = {"schema_version": 1, "profile": aws.profile,
            "created_at": datetime.now(timezone.utc).isoformat(), "regions": [],
            "resources": [], "checks": [], "errors": [],
            "limitations": ["Inventory is not exhaustive and cannot prove zero AWS costs.",
                "Risk labels are qualitative, not price estimates. Counts can overlap.",
                "Ownership, Terraform management and deletion safety are not established by scan."]}

    def items(self, service: str, region: str, operation: str, result: str, **kwargs) -> list:
        return [row for page in pages(self.aws.client(service, region), operation, **kwargs)
                for row in records(page, result)]

    def check(self, region: str, name: str, action: Callable) -> None:
        entry = {"region": region, "check": name, "status": "complete"}
        try:
            action()
        except Exception as exc:
            entry["status"] = "incomplete"
            self.report["errors"].append({"region": region, "check": name,
                                           "code": error_code(exc)})
        self.report["checks"].append(entry)

    def add(self, region: str, kind: str, identifier: str, risk: str, details: dict) -> None:
        risk, note = analyze(kind, risk, details)
        resource = {"region": region, "kind": kind, "id": identifier,
                    "risk": risk, "details": details, "cost_note": note}
        if not any((r["region"], r["kind"], r["id"]) == (region, kind, identifier)
                   for r in self.report["resources"]):
            self.report["resources"].append(resource)

    def basic(self, region: str, spec: Check) -> None:
        for page in pages(self.aws.client(spec.service, region), spec.operation, **spec.params):
            for row in records(page, spec.result):
                details = {key: extract(row, key) for key in spec.fields}
                if spec.kind == "Network Interface":
                    details["public_ipv4_addresses"] = sorted({
                        ip["Association"]["PublicIp"] for ip in row.get("PrivateIpAddresses", [])
                        if ip.get("Association", {}).get("PublicIp")})
                self.add(region, spec.kind, row[spec.identifier], spec.risk, details)

    def ecs(self, region: str) -> None:
        for arn in self.items("ecs", region, "list_clusters", "clusterArns"):
            self.add(region, "ECS Cluster", arn, "INFO", {})
            def services(cluster=arn):
                for service in self.items("ecs", region, "list_services", "serviceArns", cluster=cluster):
                    result = self.aws.client("ecs", region).describe_services(cluster=cluster, services=[service])
                    if result.get("failures"):
                        raise RuntimeError("ECSDescribeFailure")
                    for row in result["services"]:
                        self.add(region, "ECS Service", row["serviceArn"], "HIGH" if row["desiredCount"] else "INFO",
                                 {k: row.get(k) for k in ("desiredCount", "runningCount", "pendingCount", "launchType", "clusterArn", "loadBalancers")})
            self.check(region, f"ecs.services:{arn}", services)
            def tasks(cluster=arn):
                for desired in ("RUNNING", "STOPPED"):
                    for task in self.items("ecs", region, "list_tasks", "taskArns", cluster=cluster, desiredStatus=desired):
                        result = self.aws.client("ecs", region).describe_tasks(cluster=cluster, tasks=[task])
                        if result.get("failures"):
                            raise RuntimeError("ECSTaskDescribeFailure")
                        for row in result["tasks"]:
                            self.add(region, "ECS Task", row["taskArn"], "INFO" if row.get("lastStatus") == "STOPPED" else "HIGH",
                                     {k: row.get(k) for k in ("lastStatus", "desiredStatus", "launchType", "clusterArn", "cpu", "memory")})
            self.check(region, f"ecs.tasks:{arn}", tasks)

    def nested(self, region: str) -> None:
        def ecr():
            for row in self.items("ecr", region, "describe_repositories", "repositories"):
                self.add(region, "ECR Repository", row["repositoryArn"], "MEDIUM", {"repositoryName": row["repositoryName"], "image_count": None})
                def images(repo=row):
                    values = self.items("ecr", region, "describe_images", "imageDetails", repositoryName=repo["repositoryName"])
                    resource = next(r for r in self.report["resources"] if r["id"] == repo["repositoryArn"])
                    resource["details"].update(image_count=len(values), image_bytes=sum(v.get("imageSizeInBytes", 0) for v in values))
                self.check(region, f"ecr.images:{row['repositoryName']}", images)
        self.check(region, "ecr.repositories", ecr)
        def eks():
            for name in self.items("eks", region, "list_clusters", "clusters"):
                self.add(region, "EKS Cluster", name, "HIGH", {})
                def nodes(cluster=name):
                    for group in self.items("eks", region, "list_nodegroups", "nodegroups", clusterName=cluster):
                        self.add(region, "EKS Node Group", f"{cluster}/{group}", "HIGH", {"cluster": cluster})
                self.check(region, f"eks.nodegroups:{name}", nodes)
        self.check(region, "eks.clusters", eks)
        def dynamodb():
            for name in self.items("dynamodb", region, "list_tables", "TableNames"):
                self.add(region, "DynamoDB Table", name, "MEDIUM", {})
        self.check(region, "dynamodb.tables", dynamodb)
        def backup():
            for vault in self.items("backup", region, "list_backup_vaults", "BackupVaultList"):
                name = vault["BackupVaultName"]
                def recovery(vault_name=name):
                    for row in self.items("backup", region, "list_recovery_points_by_backup_vault", "RecoveryPoints", BackupVaultName=vault_name):
                        self.add(region, "Backup Recovery Point", row["RecoveryPointArn"], "MEDIUM",
                                 {k: row.get(k) for k in ("Status", "BackupSizeInBytes", "ResourceType")})
                self.check(region, f"backup.recovery:{name}", recovery)
        self.check(region, "backup.vaults", backup)

    def s3_metrics(self) -> None:
        for resource in list(self.report["resources"]):
            if resource["kind"] != "S3 Bucket":
                continue
            name = resource["id"]
            def metrics(bucket=name, item=resource):
                response = self.aws.client("s3", self.aws.region).get_bucket_location(Bucket=bucket)
                location = response.get("LocationConstraint") or "us-east-1"
                location = "eu-west-1" if location == "EU" else location
                item["details"]["BucketRegion"] = location
                end = datetime.now(timezone.utc)
                result = self.aws.client("cloudwatch", location).get_metric_statistics(
                    Namespace="AWS/S3", MetricName="BucketSizeBytes",
                    Dimensions=[{"Name": "BucketName", "Value": bucket},
                                {"Name": "StorageType", "Value": "StandardStorage"}],
                    StartTime=end - timedelta(days=3), EndTime=end, Period=86400, Statistics=["Average"])
                points = sorted(result["Datapoints"], key=lambda p: p["Timestamp"])
                item["details"]["standard_storage_metric"] = (
                    {"bytes": points[-1]["Average"], "timestamp": points[-1]["Timestamp"].isoformat()} if points else None)
                item["details"]["metric_scope"] = "Delayed StandardStorage only; missing is unknown, not zero."
            self.check("global", f"s3.metrics:{name}", metrics)

    def scan(self, all_regions: bool = False) -> dict:
        self.report.update(self.aws.identity())
        regions = [self.aws.region]
        if all_regions:
            try:
                regions = self.aws.regions()
                if not regions:
                    raise RuntimeError("EmptyRegionDiscovery")
            except Exception as exc:
                self.report["errors"].append({"region": "global", "check": "region_discovery", "code": error_code(exc)})
                regions = []
        self.report["regions"] = regions
        for region in regions:
            print(f"Scanning {region} ...", flush=True)
            for spec in REGIONAL:
                self.check(region, f"{spec.service}.{spec.operation}:{spec.kind}", lambda s=spec, r=region: self.basic(r, s))
            self.check(region, "ecs.clusters", lambda r=region: self.ecs(r))
            self.nested(region)
        for spec in GLOBAL:
            self.check("global", f"{spec.service}.{spec.operation}", lambda s=spec: self.basic("global", s))
        self.s3_metrics()
        self.report["coverage"] = "incomplete" if self.report["errors"] else "complete_for_planned_checks"
        self.report["region_status"] = {r: "incomplete" if any(e["region"] == r for e in self.report["errors"])
                                        else "complete_for_planned_checks" for r in [*regions, "global"]}
        return self.report
