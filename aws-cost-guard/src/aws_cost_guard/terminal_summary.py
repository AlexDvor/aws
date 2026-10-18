"""Beginner-oriented post-lab checklist; no claim of zero account costs."""
from collections import Counter
from textwrap import wrap


def table(headers: list[str], rows: list[list[object]], widths: list[int]) -> str:
    """ASCII borders and wrapped cells keep long ARNs readable in Git Bash."""
    def clean(value: object) -> str:
        return "".join(c if c.isprintable() else " " for c in str(value))
    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    lines = [border]
    for index, row in enumerate([headers, *rows]):
        cells = [wrap(clean(value), width=w, break_long_words=True, break_on_hyphens=False) or [""]
                 for value, w in zip(row, widths)]
        for line in range(max(map(len, cells))):
            lines.append("| " + " | ".join((cell[line] if line < len(cell) else "").ljust(w)
                                           for cell, w in zip(cells, widths)) + " |")
        lines.append(border)
    return "\n".join(lines)


def activity(resource: dict) -> str:
    """Only claim activity when explicit runtime evidence is available."""
    details = resource["details"]
    if resource["kind"] == "EC2 Instance":
        return details.get("State.Name") or "unknown"
    if resource["kind"] == "ECS Task":
        return details.get("lastStatus") or "unknown"
    if resource["kind"] == "ECS Service":
        return f"desired={details.get('desiredCount', '?')}, running={details.get('runningCount', '?')}, pending={details.get('pendingCount', '?')}"
    for key in ("DBInstanceStatus", "Status", "LifeCycleState", "State.Code", "State"):
        if isinstance(details.get(key), str):
            return details[key]
    return "usage/activity unknown"


def confirmed_active(resource: dict) -> bool:
    details = resource["details"]
    if resource["kind"] == "EC2 Instance":
        return details.get("State.Name") in ("running", "pending", "stopping")
    if resource["kind"] == "ECS Task":
        return details.get("lastStatus") in ("RUNNING", "PENDING", "PROVISIONING", "ACTIVATING", "STOPPING", "DEACTIVATING")
    if resource["kind"] == "ECS Service":
        return any((details.get(k) or 0) > 0 for k in ("desiredCount", "runningCount", "pendingCount"))
    return False


def summary(report: dict, all_regions: bool = False) -> str:
    """Prioritize things to review, keeping infrastructure context unobtrusive."""
    resources = report["resources"]
    active = [r for r in resources if confirmed_active(r)]
    stopped = [r for r in resources if r["kind"] == "EC2 Instance" and r["details"].get("State.Name") == "stopped"]
    remaining = [r for r in resources if r["risk"] != "INFO" and r not in active and r not in stopped]
    context = [r for r in resources if r["risk"] == "INFO" and r not in active and r not in stopped]
    lines = ["AWS COST GUARD - POST-LAB CHECK", f"Account: {report['account']} | Profile: {report['profile']}",
             "Regions checked: " + (", ".join(report["regions"]) or "NONE"), ""]
    if report["errors"]:
        lines += ["[INCOMPLETE] Some checks failed. Unobserved resources may still exist."]
    elif active or stopped or remaining:
        lines += ["[REVIEW NEEDED] Resources remain. Review the items below after your lab."]
    else:
        lines += ["[NO COST FLAGS FOUND] No potential cost sources detected by planned checks."]
    lines += ["", table(["Category", "Count"], [
        ["Active compute / requested ECS tasks", len(active)],
        ["Stopped EC2 - check disks and addresses", len(stopped)],
        ["Other potential cost sources", len(remaining)],
        ["Network / other context", len(context)],
        ["Failed checks", len(report["errors"])],
    ], [44, 7])]
    def section(title: str, rows: list[dict]) -> None:
        if not rows:
            return
        lines.extend(["", title, table(
            ["Region", "Resource / ID", "Risk", "Status / cost note"],
            [[r["region"], f"{r['kind']} / {r['id']}", r["risk"],
              f"{activity(r)}; {r['cost_note']}"] for r in rows],
            [14, 30, 6, 38])])
    section("ACTIVE COMPUTE / ECS SERVICES", active)
    section("STOPPED EC2 - REVIEW RETAINED STORAGE", stopped)
    section("OTHER POTENTIAL COST SOURCES", remaining)
    if context:
        counts = Counter((r["region"], r["kind"]) for r in context)
        lines += ["", "NETWORK / OTHER CONTEXT", table(
            ["Region", "Resource", "Count"],
            [[region, kind, count] for (region, kind), count in sorted(counts.items())],
            [14, 38, 7]),
            "Context objects are not evidence of running servers or applications."]
    if report["errors"]:
        lines += ["", "FAILED CHECKS", table(
            ["Region", "Check", "Error"],
            [[e["region"], e["check"], e["code"]] for e in report["errors"]],
            [14, 44, 26])]
    lines += ["", "NEXT STEP: Review ownership and dependencies before manual cleanup.",
              "For Terraform-managed resources, review the correct root module/workspace.",
              "Nothing was stopped or deleted. Risk flags are not actual charges.",
              "No flags does not prove zero costs; unsupported services and delayed Billing remain possible."]
    if not all_regions:
        lines.append("Other regions were NOT scanned. Use --all-regions to check enabled regions.")
    lines.append("Global checks cover S3 buckets and Route 53 hosted zones only.")
    if "billing" in report:
        billing = report["billing"]
        if "period" in billing:
            lines.append("Reported Billing totals (delayed/possibly estimated): " + str(billing["period"]["totals"]))
        else:
            lines.append("Billing: " + billing.get("status", "unknown"))
    return "\n".join(lines)
