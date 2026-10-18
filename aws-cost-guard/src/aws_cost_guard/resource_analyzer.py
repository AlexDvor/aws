"""Qualitative cost signals, never a price or a deletion authorization."""
from typing import Any


def extract(value: Any, path: str) -> Any:
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def analyze(kind: str, risk: str, details: dict) -> tuple[str, str]:
    note = "Potential usage/storage charges; verify Billing and ownership."
    if kind == "EC2 Instance" and details.get("State.Name") == "stopped":
        return "MEDIUM", "Compute stopped; EBS and retained public IPv4 can still incur charges."
    if kind == "Network Interface" and (details.get("Association.PublicIp") or details.get("public_ipv4_addresses")):
        return "MEDIUM", "Public IPv4 may be billable; may overlap an Elastic IP entry."
    if kind == "VPC Endpoint" and details.get("VpcEndpointType") == "Gateway":
        return "INFO", "Gateway endpoint; related service/data transfer charges need separate review."
    if details.get("State") in ("deleted", "deleting"):
        return "INFO", "Deletion state observed; verify completion and outstanding charges."
    if risk == "INFO":
        note = "Dependency/context inventory; existence alone does not imply a charge."
    return risk, note
