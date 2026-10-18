import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aws_cost_guard.terminal_summary import summary, table


class SummaryTests(unittest.TestCase):
    def report(self, resources=None, errors=None):
        return {"account": "123", "profile": "test", "regions": ["eu-south-2"],
                "resources": resources or [], "errors": errors or []}

    def resource(self, kind, details, risk="MEDIUM"):
        return {"kind": kind, "id": "example", "region": "eu-south-2", "risk": risk,
                "details": details, "cost_note": "Review retained resources."}

    def test_default_network_is_context(self):
        text = summary(self.report([self.resource("VPC", {"IsDefault": True}, "INFO")]))
        self.assertIn("[NO COST FLAGS FOUND]", text)
        self.assertIn("Network / other context", text)
        self.assertIn("Other regions were NOT scanned", text)

    def test_stopped_ec2_is_not_active_but_needs_review(self):
        text = summary(self.report([self.resource("EC2 Instance", {"State.Name": "stopped"})]))
        self.assertIn("[REVIEW NEEDED]", text)
        self.assertNotIn("\nACTIVE COMPUTE / ECS SERVICES\n", text)
        self.assertIn("STOPPED EC2 - REVIEW RETAINED STORAGE", text)

    def test_idle_lambda_is_not_claimed_running(self):
        text = summary(self.report([self.resource("Lambda Function", {})]), True)
        self.assertIn("usage/activity unknown", text)
        self.assertIn("OTHER POTENTIAL COST SOURCES", text)
        self.assertNotIn("Other regions were NOT scanned", text)

    def test_errors_prevent_no_flags_banner(self):
        text = summary(self.report(errors=[{"region": "r", "check": "ec2", "code": "AccessDenied"}]))
        self.assertIn("[INCOMPLETE]", text)
        self.assertNotIn("[NO COST FLAGS FOUND]", text)
        self.assertIn("AccessDenied", text)

    def test_running_compute_is_visible(self):
        text = summary(self.report([self.resource("EC2 Instance", {"State.Name": "running"}, "HIGH")]))
        self.assertIn("ACTIVE COMPUTE / ECS SERVICES", text)
        self.assertIn("running;", text)

    def test_wrapped_identifiers_keep_table_aligned(self):
        rendered = table(["ID", "State"], [["arn:" + "x" * 150, "running\nnow"]], [20, 12])
        self.assertEqual(len({len(line) for line in rendered.splitlines()}), 1)
        self.assertEqual(rendered.count("x"), 150)
