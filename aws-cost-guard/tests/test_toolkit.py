"""Offline regression tests: no credentials or network required."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from botocore.exceptions import ClientError
from aws_cost_guard.aws_session import pages
from aws_cost_guard.cli import main, parser
from aws_cost_guard.scanner import Scanner
from aws_cost_guard.services.catalog import Check, REGIONAL, GLOBAL
from aws_cost_guard.cost_analyzer import period_costs
from aws_cost_guard.cleanup_planner import cleanup_plan
from aws_cost_guard.report_generator import diff, save
from aws_cost_guard.terraform_analyzer import terraform_check


class ToolkitTests(unittest.TestCase):
    def aws(self):
        aws = MagicMock()
        aws.profile, aws.region = "test", "eu-south-2"
        aws.identity.return_value = {"account": "123456789012", "role_arn": "arn:aws:iam::123456789012:role/test"}
        return aws

    def test_pagination(self):
        client = MagicMock()
        client.get_paginator.return_value.paginate.return_value = [{"items": [1]}, {"items": [2]}]
        self.assertEqual(len(list(pages(client, "list_items"))), 2)
        client.get_paginator.assert_called_once_with("list_items")

    def test_unhandled_pagination_fails_closed(self):
        client = MagicMock()
        client.can_paginate.return_value = False
        client.list_items.return_value = {"NextToken": "more"}
        with self.assertRaises(RuntimeError):
            list(pages(client, "list_items"))

    def test_partial_inventory_retained_on_error(self):
        scanner = Scanner(self.aws())
        spec = Check("ec2", "describe_volumes", "Volumes", "EBS Volume", "VolumeId", "MEDIUM")
        def responses(*args, **kwargs):
            yield {"Volumes": [{"VolumeId": "vol-1"}]}
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "secret-value"}}, "DescribeVolumes")
        with patch("aws_cost_guard.scanner.pages", responses):
            scanner.check("eu-south-2", "volumes", lambda: scanner.basic("eu-south-2", spec))
        self.assertEqual(scanner.report["resources"][0]["id"], "vol-1")
        self.assertEqual(scanner.report["errors"][0]["code"], "AccessDenied")
        self.assertNotIn("secret-value", json.dumps(scanner.report))

    def test_discovery_failure_not_silently_single_region(self):
        aws = self.aws()
        aws.regions.side_effect = RuntimeError()
        scanner = Scanner(aws)
        with patch("aws_cost_guard.scanner.GLOBAL", []):
            result = scanner.scan(True)
        self.assertEqual(result["regions"], [])
        self.assertEqual(result["coverage"], "incomplete")

    def test_stopped_instance_cost_risk(self):
        scanner = Scanner(self.aws())
        scanner.add("r", "EC2 Instance", "i-1", "HIGH", {"State.Name": "stopped"})
        self.assertEqual(scanner.report["resources"][0]["risk"], "MEDIUM")

    def test_cost_pagination_and_decimal_account_scope(self):
        aws = self.aws()
        def page(service, amount, token=None):
            result = {"ResultsByTime": [{"Estimated": True, "TimePeriod": {"Start": "2026-01-01"},
                "Groups": [{"Keys": [service], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}]}]}
            if token:
                result["NextPageToken"] = token
            return result
        aws.client.return_value.get_cost_and_usage.side_effect = [page("EC2", "0.1", "next"), page("S3", "0.2")]
        result = period_costs(aws, "123456789012", "2026-01-01", "2026-01-02")
        self.assertEqual(result["totals"], {"USD": "0.3"})
        request = aws.client.return_value.get_cost_and_usage.call_args.kwargs
        self.assertEqual(request["Filter"]["Dimensions"]["Values"], ["123456789012"])
        self.assertEqual(request["NextPageToken"], "next")

    def test_cleanup_never_authorizes_deletion(self):
        report = {"account": "1", "coverage": "incomplete", "resources": [
            {"region": "r", "kind": "VPC", "id": "default", "risk": "INFO", "details": {"IsDefault": True}},
            {"region": "r", "kind": "EBS Volume", "id": "vol", "risk": "MEDIUM", "details": {"Attachments": [{"InstanceId": "i"}]}}]}
        result = cleanup_plan(report)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertIn("UNKNOWN", result["candidates"][0]["deletion_safety"])
        self.assertEqual(result["mode"], "dry-run-only")
        with self.assertRaises(SystemExit):
            parser().parse_args(["cleanup", "--execute"])

    def test_terraform_output_allowlist_and_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "main.tf").write_text("")
            (path / "terraform.tfstate").write_text(json.dumps({"version": 4, "outputs": {"secret": "DO_NOT_EXPORT"}, "resources": [
                {"mode": "managed", "type": "aws_instance", "name": "lab", "instances": [{"attributes": {"id": "i-1", "user_data": "DO_NOT_EXPORT"}}]}]}))
            result = terraform_check(path, {"resources": [{"id": "i-1"}]})
            self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))
            self.assertEqual(result["comparison"][0]["observation"], "identifier_observed")

    def test_diff_never_claims_deletion_and_rejects_other_account(self):
        before = {"account": "1", "schema_version": 1, "resources": [{"region": "r", "kind": "EC2", "id": "i"}]}
        after = {"account": "1", "schema_version": 1, "resources": []}
        self.assertEqual(len(diff(before, after)["not_observed_after"]), 1)
        after["account"] = "2"
        with self.assertRaises(ValueError):
            diff(before, after)

    def test_terraform_credential_identifiers_are_not_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "terraform.tfstate").write_text(json.dumps({"version": 4, "resources": [
                {"mode": "managed", "type": "aws_iam_access_key", "name": "lab", "instances": [
                    {"attributes": {"id": "CREDENTIAL_DO_NOT_EXPORT", "secret": "SECRET_DO_NOT_EXPORT"}}]}]}))
            result = terraform_check(path)
            self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))
            self.assertEqual(result["managed_resources"][0]["identifiers"], [])

    def test_report_files(self):
        scanner = Scanner(self.aws())
        scanner.report.update(scanner.aws.identity(), coverage="incomplete", region_status={"r": "incomplete"})
        with tempfile.TemporaryDirectory() as directory:
            paths = save(scanner.report, Path(directory))
            self.assertEqual(json.loads(paths[0].read_text())["coverage"], "incomplete")
            self.assertIn("not actual charges", paths[1].read_text())

    def test_api_catalog_matches_sdk_models_without_network(self):
        import boto3
        from botocore.validate import validate_parameters
        session = boto3.Session(aws_access_key_id="testing", aws_secret_access_key="testing", region_name="us-east-1")
        for spec in REGIONAL + GLOBAL:
            client = session.client(spec.service)
            self.assertTrue(hasattr(client, spec.operation), spec)
            operation = client.meta.service_model.operation_model(client.meta.method_to_api_mapping[spec.operation])
            validate_parameters(spec.params, operation.input_shape)
            shape = operation.output_shape
            for field in spec.result.split("."):
                self.assertIn(field, shape.members, spec)
                shape = shape.members[field].member
            self.assertIn(spec.identifier, shape.members, spec)

    def test_audit_writes_reports_when_billing_denied(self):
        import contextlib
        import io
        aws = self.aws()
        aws.client.return_value.can_paginate.return_value = False
        # Empty successful inventory for every declared API.
        for spec in REGIONAL + GLOBAL:
            getattr(aws.client.return_value, spec.operation).return_value = {}
        for operation in ("list_clusters", "describe_repositories", "list_tables", "list_backup_vaults"):
            getattr(aws.client.return_value, operation).return_value = {}
        denial = ClientError({"Error": {"Code": "AccessDenied"}}, "GetCostAndUsage")
        with tempfile.TemporaryDirectory() as directory:
            with patch("aws_cost_guard.cli.AWS", return_value=aws), patch("aws_cost_guard.cli.costs", side_effect=denial), contextlib.redirect_stdout(io.StringIO()):
                status = main(["audit", "--reports-dir", directory])
            self.assertEqual(status, 2)
            report = json.loads(next(Path(directory).glob("*.json")).read_text())
            self.assertEqual(report["coverage"], "incomplete")
            self.assertEqual(report["region_status"]["global"], "incomplete")
            self.assertEqual(report["billing"]["code"], "AccessDenied")
            self.assertGreater(len(report["checks"]), 30)

    def test_nested_ecs_preserves_desired_and_launch_type(self):
        aws = self.aws()
        scanner = Scanner(aws)
        def items(service, region, operation, result, **kwargs):
            return {"list_clusters": ["cluster"], "list_services": ["service"],
                    "list_tasks": ["task"] if kwargs.get("desiredStatus") == "RUNNING" else []}[operation]
        scanner.items = items
        aws.client.return_value.describe_services.return_value = {"services": [{"serviceArn": "service", "desiredCount": 2, "runningCount": 1, "pendingCount": 1}]}
        aws.client.return_value.describe_tasks.return_value = {"tasks": [{"taskArn": "task", "lastStatus": "RUNNING", "launchType": "FARGATE"}]}
        scanner.ecs("region")
        resources = {r["kind"]: r for r in scanner.report["resources"]}
        self.assertEqual(resources["ECS Service"]["details"]["desiredCount"], 2)
        self.assertEqual(resources["ECS Task"]["details"]["launchType"], "FARGATE")

    def test_bad_days_rejected_before_session(self):
        with patch("aws_cost_guard.cli.AWS") as aws:
            self.assertEqual(main(["costs", "--days", "0"]), 1)
            aws.assert_not_called()


if __name__ == "__main__":
    unittest.main()
