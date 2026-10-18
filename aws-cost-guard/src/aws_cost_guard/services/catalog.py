"""Explicit API/field allowlists avoid exporting raw AWS responses."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Check:
    service: str
    operation: str
    result: str
    kind: str
    identifier: str
    risk: str
    fields: tuple[str, ...] = ()
    params: dict = field(default_factory=dict)


REGIONAL = [
    Check("ec2", "describe_instances", "Reservations.Instances", "EC2 Instance", "InstanceId", "HIGH", ("State.Name", "InstanceType", "VpcId", "SubnetId", "PublicIpAddress"), {"Filters": [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]}),
    Check("ec2", "describe_volumes", "Volumes", "EBS Volume", "VolumeId", "MEDIUM", ("State", "Size", "VolumeType", "Attachments")),
    Check("ec2", "describe_snapshots", "Snapshots", "EBS Snapshot", "SnapshotId", "MEDIUM", ("State", "VolumeSize"), {"OwnerIds": ["self"]}),
    Check("ec2", "describe_addresses", "Addresses", "Elastic IP", "AllocationId", "MEDIUM", ("PublicIp", "AssociationId", "NetworkInterfaceId", "InstanceId")),
    Check("ec2", "describe_network_interfaces", "NetworkInterfaces", "Network Interface", "NetworkInterfaceId", "INFO", ("Status", "VpcId", "SubnetId", "Association.PublicIp", "Attachment.InstanceId", "InterfaceType")),
    Check("ec2", "describe_nat_gateways", "NatGateways", "NAT Gateway", "NatGatewayId", "HIGH", ("State", "VpcId", "SubnetId")),
    Check("ec2", "describe_vpc_endpoints", "VpcEndpoints", "VPC Endpoint", "VpcEndpointId", "MEDIUM", ("State", "VpcId", "VpcEndpointType", "ServiceName")),
    Check("ec2", "describe_vpn_gateways", "VpnGateways", "VPN Gateway", "VpnGatewayId", "INFO", ("State", "VpcAttachments")),
    Check("ec2", "describe_vpn_connections", "VpnConnections", "VPN Connection", "VpnConnectionId", "HIGH", ("State", "VpnGatewayId", "TransitGatewayId")),
    Check("ec2", "describe_vpcs", "Vpcs", "VPC", "VpcId", "INFO", ("State", "IsDefault")),
    Check("ec2", "describe_subnets", "Subnets", "Subnet", "SubnetId", "INFO", ("VpcId", "State")),
    Check("ec2", "describe_internet_gateways", "InternetGateways", "Internet Gateway", "InternetGatewayId", "INFO", ("Attachments",)),
    Check("ec2", "describe_security_groups", "SecurityGroups", "Security Group", "GroupId", "INFO", ("VpcId", "GroupName")),
    Check("ec2", "describe_route_tables", "RouteTables", "Route Table", "RouteTableId", "INFO", ("VpcId", "Associations")),
    Check("elbv2", "describe_load_balancers", "LoadBalancers", "Load Balancer", "LoadBalancerArn", "HIGH", ("State.Code", "Type", "VpcId", "LoadBalancerName")),
    Check("elbv2", "describe_target_groups", "TargetGroups", "Target Group", "TargetGroupArn", "INFO", ("LoadBalancerArns", "VpcId", "TargetGroupName")),
    Check("elb", "describe_load_balancers", "LoadBalancerDescriptions", "Classic Load Balancer", "LoadBalancerName", "HIGH", ("VPCId", "Instances")),
    Check("lambda", "list_functions", "Functions", "Lambda Function", "FunctionArn", "LOW", ("Runtime", "MemorySize", "FunctionName")),
    Check("rds", "describe_db_instances", "DBInstances", "RDS Instance", "DBInstanceArn", "HIGH", ("DBInstanceStatus", "DBInstanceClass", "AllocatedStorage", "DBClusterIdentifier")),
    Check("rds", "describe_db_clusters", "DBClusters", "RDS Cluster", "DBClusterArn", "HIGH", ("Status", "Engine", "DBClusterMembers")),
    Check("rds", "describe_db_snapshots", "DBSnapshots", "RDS Snapshot", "DBSnapshotArn", "MEDIUM", ("Status", "AllocatedStorage", "SnapshotType")),
    Check("rds", "describe_db_cluster_snapshots", "DBClusterSnapshots", "RDS Cluster Snapshot", "DBClusterSnapshotArn", "MEDIUM", ("Status", "AllocatedStorage", "SnapshotType")),
    Check("efs", "describe_file_systems", "FileSystems", "EFS File System", "FileSystemId", "MEDIUM", ("LifeCycleState", "SizeInBytes", "NumberOfMountTargets")),
    Check("logs", "describe_log_groups", "logGroups", "CloudWatch Log Group", "logGroupName", "LOW", ("storedBytes", "retentionInDays")),
    Check("cloudwatch", "describe_alarms", "MetricAlarms", "CloudWatch Alarm", "AlarmArn", "LOW", ("StateValue", "AlarmName")),
    Check("cloudwatch", "describe_alarms", "CompositeAlarms", "CloudWatch Composite Alarm", "AlarmArn", "LOW", ("StateValue", "AlarmName"), {"AlarmTypes": ["CompositeAlarm"]}),
]

GLOBAL = [
    Check("s3", "list_buckets", "Buckets", "S3 Bucket", "Name", "MEDIUM", ("BucketRegion",)),
    Check("route53", "list_hosted_zones", "HostedZones", "Route 53 Hosted Zone", "Id", "MEDIUM", ("Name", "ResourceRecordSetCount")),
]
