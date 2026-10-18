"""CLI commands: all AWS operations are read-only."""
import argparse
import json
import sys
from pathlib import Path

from .aws_session import AWS, error_code
from .cleanup_planner import cleanup_plan
from .cost_analyzer import budgets, costs
from .report_generator import diff, markdown, save
from .scanner import Scanner
from .terraform_analyzer import terraform_check
from .terminal_summary import summary


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read-only AWS resource and cost audit. No deletion commands.")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("scan", "audit", "cleanup", "costs", "budget"):
        command = commands.add_parser(name)
        command.add_argument("--profile", default="admin")
        region = command.add_mutually_exclusive_group()
        region.add_argument("--region")
        region.add_argument("--all-regions", action="store_true")
        if name in ("audit", "costs"):
            command.add_argument("--days", type=int, default=30)
        if name in ("scan", "audit"):
            command.add_argument("--details", action="store_true", help="Show the full technical inventory instead of the post-lab checklist")
        if name == "audit":
            command.add_argument("--reports-dir", type=Path, default=Path(__file__).resolve().parents[2] / "reports")
            command.add_argument("--skip-costs", action="store_true", help="Avoid Cost Explorer API requests (which may incur charges)")
        if name == "cleanup":
            command.add_argument("--dry-run", action="store_true", default=True)
    compare = commands.add_parser("diff")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    terraform = commands.add_parser("terraform-check")
    terraform.add_argument("--path", type=Path, required=True)
    terraform.add_argument("--scan-report", help="Optional audit JSON to compare identifiers")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if hasattr(args, "days") and not 1 <= args.days <= 366:
        print("ERROR: --days must be between 1 and 366", file=sys.stderr)
        return 1
    try:
        if args.command == "diff":
            result = diff(load(args.before), load(args.after))
        elif args.command == "terraform-check":
            result = terraform_check(args.path, load(args.scan_report) if args.scan_report else None)
        else:
            aws = AWS(args.profile, args.region)
            if args.command in ("costs", "budget"):
                account = aws.identity()["account"]
                result = costs(aws, account, args.days) if args.command == "costs" else budgets(aws, account)
            else:
                report = Scanner(aws).scan(args.all_regions)
                if args.command == "audit":
                    if args.skip_costs:
                        report["billing"] = {"status": "skipped", "reason": "--skip-costs"}
                    else:
                        print("Querying Cost Explorer (API requests may incur charges) ...", flush=True)
                        try:
                            report["billing"] = costs(aws, report["account"], args.days)
                        except Exception as exc:
                            report["billing"] = {"status": "incomplete", "code": error_code(exc)}
                            report["errors"].append({"region": "global", "check": "cost_explorer", "code": error_code(exc)})
                            report["coverage"] = "incomplete"
                            report["region_status"]["global"] = "incomplete"
                    paths = save(report, args.reports_dir)
                    print("Reports: " + ", ".join(str(p) for p in paths))
                if args.command == "cleanup":
                    result = cleanup_plan(report)
                    result["errors"] = report["errors"]
                else:
                    print(markdown(report) if args.details else summary(report, args.all_regions))
                    return 2 if report["errors"] else 0
                print(json.dumps(result, indent=2, default=str))
                return 2 if report["errors"] else 0
        print(json.dumps(result, indent=2, default=str))
        return 2 if result.get("errors") else 0
    except Exception as exc:
        print(f"ERROR: {error_code(exc)}. Check profile/MFA, permissions and input files; no resources changed.", file=sys.stderr)
        return 1
