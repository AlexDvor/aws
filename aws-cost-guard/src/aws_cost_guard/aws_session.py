"""Use the AWS credential provider chain; never persist credentials."""
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def error_code(error: Exception) -> str:
    """Only expose a code: service error messages may contain sensitive input."""
    if isinstance(error, ClientError):
        return error.response.get("Error", {}).get("Code", "ClientError")
    return type(error).__name__


class AWS:
    def __init__(self, profile: str, region: str | None = None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.region = region or self.session.region_name or "us-east-1"
        self.profile = profile
        self.config = Config(retries={"mode": "standard", "total_max_attempts": 5},
                             connect_timeout=10, read_timeout=30)
        self._clients: dict[tuple[str, str], Any] = {}

    def client(self, service: str, region: str) -> Any:
        if region == "global":
            region = self.region
        key = service, region
        if key not in self._clients:
            self._clients[key] = self.session.client(service, region_name=region,
                                                      config=self.config)
        return self._clients[key]

    def identity(self) -> dict:
        result = self.client("sts", self.region).get_caller_identity()
        return {"account": result["Account"], "role_arn": result["Arn"]}

    def regions(self) -> list[str]:
        response = self.client("ec2", self.region).describe_regions(AllRegions=False)
        return sorted(r["RegionName"] for r in response["Regions"])


def pages(client: Any, operation: str, **kwargs: Any):
    """Use SDK pagination, including service-specific token conventions."""
    if client.can_paginate(operation):
        yield from client.get_paginator(operation).paginate(**kwargs)
    else:
        response = getattr(client, operation)(**kwargs)
        yield response
        if any(response.get(k) for k in ("NextToken", "nextToken", "NextMarker",
                                         "Marker", "ContinuationToken")):
            raise RuntimeError("PaginationUnavailable")
