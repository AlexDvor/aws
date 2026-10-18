"""Plans only: deliberately contains no AWS mutation operations."""


def cleanup_plan(report: dict) -> dict:
    candidates = []
    for resource in report["resources"]:
        if resource["kind"] == "VPC" and resource["details"].get("IsDefault"):
            continue
        candidates.append({"region": resource["region"], "kind": resource["kind"],
            "id": resource["id"], "risk": resource["risk"],
            "observed_dependencies": {k: v for k, v in resource["details"].items()
                if v is not None and any(word in k.lower() for word in ("attach", "vpc", "subnet", "cluster", "loadbalancer", "mount"))},
            "deletion_safety": "UNKNOWN — manual ownership and dependency verification required",
            "recommendation": "If Terraform-managed, review terraform plan and terraform destroy in the correct root module. Otherwise inspect dependencies in AWS Console; inventory is not deletion authorization."})
    return {"mode": "dry-run-only", "account": report["account"],
            "coverage": report["coverage"], "candidates": candidates,
            "notice": "No resources have been deleted. Dependency hints are incomplete, not a safe deletion order. Default VPCs excluded; related default resources may appear as context. No execute mode exists."}
