"""Read local state with a strict output allowlist. Never run Terraform."""
import json
from pathlib import Path


# Arbitrary Terraform IDs can themselves be credentials (e.g. IAM access keys).
# Export identifiers only for known infrastructure resource types.
IDENTIFIER_TYPES = {
    "aws_instance", "aws_ecs_cluster", "aws_ecs_service", "aws_eks_cluster",
    "aws_eks_node_group", "aws_lambda_function", "aws_ecr_repository",
    "aws_lb", "aws_alb", "aws_elb", "aws_lb_target_group", "aws_alb_target_group",
    "aws_nat_gateway", "aws_eip", "aws_network_interface", "aws_vpc_endpoint",
    "aws_vpn_gateway", "aws_vpn_connection", "aws_vpc", "aws_subnet",
    "aws_internet_gateway", "aws_security_group", "aws_route_table",
    "aws_ebs_volume", "aws_ebs_snapshot", "aws_s3_bucket", "aws_db_instance",
    "aws_rds_cluster", "aws_db_snapshot", "aws_db_cluster_snapshot",
    "aws_dynamodb_table", "aws_efs_file_system", "aws_cloudwatch_log_group",
    "aws_cloudwatch_metric_alarm", "aws_cloudwatch_composite_alarm",
    "aws_backup_vault", "aws_route53_zone",
}


def terraform_check(path: Path, scan: dict | None = None) -> dict:
    path = path.resolve()
    if not path.is_dir():
        raise ValueError("Terraform path must be an existing directory")
    excluded = {".terraform", ".git", ".venv", "node_modules"}
    def allowed(file: Path) -> bool:
        return not excluded.intersection(file.relative_to(path).parts)
    modules = sorted({str(p.parent) for p in path.rglob("*.tf") if allowed(p)})
    resources, errors, states = [], [], []
    for state in sorted(path.rglob("*.tfstate")):
        if not allowed(state):
            continue
        states.append(str(state))
        try:
            data = json.loads(state.read_text(encoding="utf-8-sig"))
            if data.get("version") != 4:
                errors.append({"file": str(state), "code": "UnsupportedStateFormat"})
                continue
            for resource in data.get("resources", []):
                if resource.get("mode") != "managed":
                    continue
                for instance in resource.get("instances", []):
                    attributes = instance.get("attributes", {})
                    # Export identifiers only, never outputs, user_data, variables or credentials.
                    identifiers = [attributes[k] for k in ("id", "arn")
                                   if resource.get("type") in IDENTIFIER_TYPES
                                   and isinstance(attributes.get(k), str)]
                    resources.append({"state_file": str(state), "module": resource.get("module", "root"),
                                      "type": resource.get("type"), "name": resource.get("name"),
                                      "identifiers": identifiers})
        except (OSError, ValueError, TypeError, AttributeError):
            errors.append({"file": str(state), "code": "UnreadableOrInvalidState"})
    result = {"candidate_module_directories": modules, "state_files": states, "managed_resources": resources,
              "errors": errors, "notice": "Module directories are candidates, not proven deployable roots. Remote state and .terraform directories are not read. Missing local state never proves no AWS resources. Output contains infrastructure identifiers; protect reports.",
              "recommendation": "In the verified Terraform root/workspace/account, review terraform plan for drift. Only after reviewing dependencies and ownership consider terraform destroy manually. This command executes neither."}
    if scan:
        observed = {r["id"] for r in scan["resources"]}
        result["comparison"] = [{**r, "observation": "identifier_observed" if observed.intersection(r["identifiers"]) else "not_observed_or_unsupported"} for r in resources]
        result["comparison_notice"] = "Identifier comparison only, not attribute drift detection. Account/region/workspace must be verified manually; incomplete scan or unsupported resources may explain absence."
    return result
