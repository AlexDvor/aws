"""Portable JSON/Markdown reports and conservative inventory comparison."""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def markdown(report: dict) -> str:
    def safe(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# AWS COST GUARD", "", f"Account: {report['account']}",
             f"Role: {report['role_arn']}", f"Profile: {report['profile']}",
             f"Created (UTC): {report['created_at']}",
             f"Regions: {', '.join(report['regions'])}", f"Coverage: {report['coverage']}", "",
             "Risk labels are potential cost signals, not actual charges or deletion approval.", ""]
    for region, status in report["region_status"].items():
        lines += [f"## REGION: {region} — {status}", ""]
        counts = Counter(r["kind"] for r in report["resources"] if r["region"] == region)
        lines += [f"- {kind}: {count}" for kind, count in sorted(counts.items())]
        lines.append("")
    lines += ["## Resources / potential cost sources", "", "|Region|Resource|ID|Risk|Details|Cost note|", "|---|---|---|---|---|---|"]
    for r in report["resources"]:
        lines.append("|" + "|".join(safe(v) for v in (r["region"], r["kind"], r["id"], r["risk"], json.dumps(r["details"], default=str), r["cost_note"])) + "|")
    lines += ["", "## Planned check coverage", "", "|Region|Check|Status|", "|---|---|---|"]
    lines += ["|" + "|".join(safe(c[k]) for k in ("region", "check", "status")) + "|" for c in report["checks"]]
    lines += ["", "## Errors and skipped/incomplete checks", ""]
    lines += [f"- {safe(e)}" for e in report["errors"]] or ["None recorded."]
    lines += ["", "## Summary", "", f"Resources detected: {len(report['resources'])}",
              f"Potentially billable entries (may overlap): {sum(r['risk'] != 'INFO' for r in report['resources'])}",
              f"Scan errors: {len(report['errors'])}", "", "## Limitations", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    lines += ["", "## Safe cleanup recommendations", "",
              "Review ownership and dependencies manually. For Terraform-managed resources, use the correct root module and inspect terraform plan before considering terraform destroy. No deletion safety is inferred."]
    if "billing" in report:
        lines += ["", "## Billing (delayed, potentially estimated)", "", "```json", json.dumps(report["billing"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def save(report: dict, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stem = "aws-audit-" + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_%f")
    json_path, md_path = directory / f"{stem}.json", directory / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    return json_path, md_path


def diff(before: dict, after: dict) -> dict:
    if before["account"] != after["account"]:
        raise ValueError("Cannot compare different AWS accounts")
    if before.get("schema_version") != after.get("schema_version"):
        raise ValueError("Cannot compare different report schema versions")
    def index(report):
        return {(r["region"], r["kind"], r["id"]): r for r in report["resources"]}
    left, right = index(before), index(after)
    return {"appeared": [right[k] for k in sorted(right.keys() - left.keys())],
            "not_observed_after": [left[k] for k in sorted(left.keys() - right.keys())],
            "changed": [{"before": left[k], "after": right[k]} for k in sorted(left.keys() & right.keys()) if left[k] != right[k]],
            "notice": "Not observed does not prove deletion: inspect coverage, permissions, check sets and scanned regions in BOTH reports.",
            "coverage": {"before": before.get("coverage"), "after": after.get("coverage")},
            "regions": {"before": before.get("regions"), "after": after.get("regions")}}
