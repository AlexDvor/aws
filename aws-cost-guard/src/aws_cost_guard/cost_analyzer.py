"""Account-scoped Cost Explorer and Budgets, using decimal arithmetic."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .aws_session import AWS, pages


def period_costs(aws: AWS, account: str, start: str, end: str) -> dict:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    services: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    daily: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    estimated = False
    request = {"TimePeriod": {"Start": start, "End": end}, "Granularity": "DAILY",
               "Metrics": ["UnblendedCost"],
               "Filter": {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account]}},
               "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]}
    client = aws.client("ce", "us-east-1")
    seen: set[str] = set()
    while True:
        response = client.get_cost_and_usage(**request)
        for day in response.get("ResultsByTime", []):
            estimated |= day.get("Estimated", False)
            for group in day.get("Groups", []):
                metric = group["Metrics"]["UnblendedCost"]
                unit, amount = metric["Unit"], Decimal(metric["Amount"])
                totals[unit] += amount
                services[(group["Keys"][0], unit)] += amount
                daily[(day["TimePeriod"]["Start"], unit)] += amount
        token = response.get("NextPageToken")
        if not token:
            break
        if token in seen:
            raise RuntimeError("RepeatedCostExplorerToken")
        seen.add(token)
        request["NextPageToken"] = token
    return {"start": start, "end_exclusive": end, "estimated": estimated,
            "totals": {unit: str(value) for unit, value in totals.items()},
            "services": [{"service": name, "unit": unit, "amount": str(value)} for (name, unit), value in sorted(services.items())],
            "daily": [{"date": day, "unit": unit, "amount": str(value)} for (day, unit), value in sorted(daily.items())]}


def costs(aws: AWS, account: str, days: int) -> dict:
    if not 1 <= days <= 366:
        raise ValueError("days must be between 1 and 366")
    today = datetime.now(timezone.utc).date()
    # End is exclusive: tomorrow includes the current, incomplete UTC day.
    end = (today + timedelta(days=1)).isoformat()
    return {"metric": "UnblendedCost", "account": account,
            "period": period_costs(aws, account, (today - timedelta(days=days - 1)).isoformat(), end),
            "month_to_date": period_costs(aws, account, today.replace(day=1).isoformat(), end),
            "notice": "Billing is delayed and may be estimated. Not a final invoice or forecast. Zero/missing costs do not mean resources are free. Cost Explorer API requests can incur charges."}


def budgets(aws: AWS, account: str) -> dict:
    result = []
    for page in pages(aws.client("budgets", "us-east-1"), "describe_budgets", AccountId=account):
        for row in page.get("Budgets", []):
            result.append({k: row.get(k) for k in ("BudgetName", "BudgetType", "TimeUnit", "BudgetLimit", "CalculatedSpend")})
    return {"account": account, "budgets": result,
            "notice": "Budgets notify; they do not automatically stop resources."}
