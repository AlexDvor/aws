# AWS Cost Guard

A local, read-only resource and cost audit toolkit for AWS learning accounts.
Run it after a lab to discover leftover infrastructure, inspect delayed Billing
data, and prepare a manual cleanup review. Python 3.11+ is required.

**This is an MVP, not an exhaustive AWS inventory or a zero-cost guarantee.**
Risk labels are qualitative, not prices. No command creates, updates, stops or
deletes AWS resources. There is no `--execute` or `delete-all` operation.
Read-only API requests can themselves incur charges, particularly Cost Explorer.
Use `audit --skip-costs` to avoid its Billing requests.

## Daily workflow: did I forget anything running?

If you have already installed the toolkit, open Git Bash in `aws-cost-guard`
and run:

```bash
source .venv/Scripts/activate
# Choose ONE of these scopes:
python main.py scan --profile admin --region eu-south-2
python main.py scan --profile admin --all-regions
```

Enter your current MFA code if prompted. The scan is a one-time check, not a
background monitor. Run it again after each lab and after manual cleanup.
These `scan` commands do not call Cost Explorer.

The console displays ASCII tables. Read the **Category / Count** table first:

| Category | How to interpret it |
|---|---|
| Active compute / requested ECS tasks | EC2 is running/starting/stopping, or an ECS service/task still has observed/requested activity. Review if the lab is finished. Counts can overlap services and their tasks. |
| Stopped EC2 - check disks and addresses | Stopped instances remain. Review associated EBS and public addresses; stopped is not the same as deleted. |
| Other potential cost sources | Review the resource table: disks, snapshots, load balancers, NAT, databases, storage, and usage-dependent/idle services may still exist. Existence is not proof of a current charge. |
| Network / other context | Dependency objects such as a default VPC, subnets and security groups. This is not a count of running applications. |
| Failed checks | A nonzero value means visibility is incomplete. Resolve the displayed errors and rerun before drawing conclusions. |

`NO COST FLAGS FOUND` means only that the planned successful checks found no cost
flags in the selected scope. It does not certify a zero bill. `REVIEW NEEDED`
means look at the listed resource IDs/statuses; it is not deletion approval.
`INCOMPLETE` means some checks failed, even if the resource tables are empty.
With one region selected, other regions remain unchecked. Global checks cover
S3 bucket discovery and Route 53 hosted zones, not all global AWS services.

To save full JSON and Markdown reports without Cost Explorer:

```bash
python main.py audit --profile admin --all-regions --skip-costs
```

To see technical fields and per-check coverage in the terminal:

```bash
python main.py scan --profile admin --region eu-south-2 --details
```

If unwanted resources are found, use the AWS Console or the correct Terraform
project to review ownership/dependencies before manually stopping/removing them.
This application does not switch anything off for you. Then rerun the scan.

## First-time installation

Install Python 3.11+ and AWS CLI v2 first. From the repository root:

```bash
cd aws-cost-guard
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py --help
```

If venv creation cannot bootstrap pip, repair your Python installation, or use
an existing pip installation to populate the created environment:

```bash
python -m venv --without-pip .venv
py -3.13 -m pip --python .venv install -r requirements.txt
source .venv/Scripts/activate
```

The fallback uses the globally installed Python 3.13 pip to install packages into
`.venv`; replace `-3.13` with your installed version (3.11+). A `No module named
pip` message inside a `--without-pip` environment is expected: use the external
pip command above. If `Unable to copy ... venvlauncher.exe` appears, close Python
processes using that environment and check file permissions/security software
before retrying. Do not delete your project to repair a virtual environment.

If `cd aws-cost-guard` fails, your shell is in a different directory: use `pwd`
and navigate to the repository first. If activation fails, verify your location
and that environment creation finished. Activation is optional when using:

```bash
./.venv/Scripts/python.exe main.py scan --profile admin --all-regions
```

Terraform is optional and only needed for your own subsequent plan/destroy
review. The toolkit reads local state directly and never executes Terraform.
No YAML configuration is required; CLI arguments are the configuration source.

## Authentication, profiles and MFA

The default profile is `admin`. Boto3 uses standard AWS providers, including
AssumeRole and MFA configured in your existing AWS configuration. It can prompt
for MFA on the terminal. CLI cached role sessions are not guaranteed to be shared
with Boto3; another MFA prompt is normal. SSO profiles must first be logged in
with `aws sso login --profile PROFILE`.

```bash
aws --version
aws sts get-caller-identity --profile admin
python main.py scan --profile admin --region eu-south-2
```

Configure your source profile, role ARN and `mfa_serial` with the standard AWS
CLI workflow outside this repository. Never paste credentials into source,
reports, `.env`, command arguments or Git. The toolkit never writes credentials.
Reports contain account IDs, ARNs, resource names, topology and metadata: treat
them as sensitive. Reports and virtual environments are ignored by Git.

Use an appropriately scoped read-only role. Required actions correspond to
the `Describe*`, `List*` and `Get*` calls in `services/catalog.py` and
`scanner.py`, plus `sts:GetCallerIdentity`, `ec2:DescribeRegions`,
`ce:GetCostAndUsage`, `budgets:ViewBudget`, `s3:GetBucketLocation` and
`cloudwatch:GetMetricStatistics`. SCPs and service-specific permissions may
restrict discovery. Do not grant write access to make a read-only audit work.

## Commands

`scan` and `audit` show a concise post-lab checklist by default: active compute,
stopped EC2, other potential cost sources (including storage/idle services),
network/context counts and failed checks. Only explicit runtime fields are used
to label EC2/ECS activity; other resources show their observed state or unknown
usage. An empty checklist never guarantees zero costs. Use `--details` for the
full technical inventory; saved audit reports always keep full detail.

```bash
# One region, plus global S3/Route 53 discovery
python main.py scan --profile admin --region eu-south-2

# Discover enabled regions with EC2 DescribeRegions, then scan sequentially
python main.py scan --profile admin --all-regions

# Inventory + Cost Explorer + local JSON/Markdown reports
python main.py audit --profile admin --all-regions
python main.py audit --profile admin --all-regions --skip-costs
python main.py audit --profile admin --region eu-south-2 --reports-dir reports

# Actual reported usage, not a prediction of future charges
python main.py costs --profile admin --days 30
python main.py budget --profile admin

# Plans only, including observed dependency hints
python main.py cleanup --profile admin --region eu-south-2 --dry-run

# Compare audit files from the same account
python main.py diff --before reports/before.json --after reports/after.json

# Offline state analysis (no Terraform executable or AWS credentials needed)
python main.py terraform-check --path ../dz3
python main.py terraform-check --path ../dz3 --scan-report reports/after.json
```

Without `--region`, use the profile's region, falling back to `us-east-1`.
`--region` and `--all-regions` are mutually exclusive. Billing commands are
account-scoped, independent of these inventory region switches. Global service
coverage refers to the active AWS partition. Cost Explorer/Budgets currently
use the commercial `us-east-1` endpoint; other partitions may report errors.

Git Bash wrappers forward arguments (`bash scripts/audit.sh --all-regions`).
Set `PYTHON` to a Python executable path when necessary.

Exit codes: `0` completed planned checks, `1` fatal input/authentication error,
`2` incomplete checks/errors. Successful planned checks never prove the account
is clean. Failed region discovery is reported rather than silently scanning just
one region. Authentication failure stops before resource checks.

## Coverage and report interpretation

| Area | Planned inventory |
|---|---|
| Compute | EC2 pending/running/stopping/stopped, Lambda, EKS clusters/node group names |
| Containers | ECS clusters, services with desired/running/pending counts, tasks including Fargate launch type, ECR repositories with image count/bytes |
| Network | ALB/NLB, Classic ELB, target groups, NAT, EIP, ENIs with public IPv4, VPC endpoints, VPN gateways/connections, VPCs, subnets, IGWs, security groups, route tables |
| Storage/databases | EBS volumes/snapshots, S3 buckets, RDS instances/clusters and snapshots, DynamoDB table names, EFS size/mount counts |
| Monitoring | Log groups/stored bytes, metric/composite alarms, Backup recovery points |
| Global | S3 bucket discovery and Route 53 hosted zones |

S3 StandardStorage size is fetched from recent daily CloudWatch metrics. Other
storage classes are not aggregated; absent metrics mean unknown, not empty.
An ECR image count is a count of image detail records, not tags or unique layers.
EKS node group instance counts, ECS capacity-provider billing, S3 objects,
Lambda invocation metrics and detailed attribute drift are outside MVP scope.
No object contents, Lambda environment variables, ECS task secrets, VPN
configuration or Terraform outputs are exported.

Each API check and nested lookup records success or failure. SDK paginator
models are used; unsupported continuation is an error rather than truncation.
AWS standard retries use five total attempts with bounded network timeouts.
Partial discoveries remain in the report if a later page fails. `AccessDenied`,
`ExpiredToken`, throttling and other errors appear as error codes; raw service
messages are suppressed to reduce disclosure. An incomplete regional check
means the region remains incomplete, even if no resources were returned.

`HIGH` flags potentially substantial recurring costs, `MEDIUM` noticeable
storage/network/service exposure, `LOW` smaller or usage-dependent exposure,
and `INFO` dependency/context objects. These are heuristics: empty repositories
or idle functions may have zero charges, while a low-risk entry can still be
expensive under heavy usage. Counts overlap (for example EIP and ENI public
IPv4, RDS instances and clusters). Do not add risk labels into a dollar estimate.

Audit writes UTC-timestamped `reports/aws-audit-*.json` and `.md` files, with
microseconds to avoid overwriting rapid successive runs. JSON includes account,
caller ARN, regions, resources, per-check coverage, errors, limitations and
Billing results. Markdown includes human-readable summaries and cleanup advice.
Use both reports' coverage and region lists when comparing: `not_observed_after`
does **not** prove deletion. Comparisons across accounts/schema versions fail.

## Billing and budgets

Cost Explorer queries `UnblendedCost`, grouped by service and UTC day, filtered
to the caller account even when the role belongs to an Organizations payer.
It paginates and uses decimal arithmetic, preserving returned currencies rather
than assuming USD. The selected period includes today, whose data is incomplete;
the API end date is exclusive. Month-to-date is queried separately. Estimates
and delayed usage can change, and the result is not a final invoice. No dollar
forecast is inferred from resource inventory. Cost Explorer must be available
and authorized; an audit still writes inventory reports if Billing fails.

In AWS Console, open **Billing and Cost Management → Bills / Cost Explorer**
to inspect charges and dates. Check other linked accounts and subscriptions when
relevant. Inventory cannot cover all data transfer, Marketplace, reservations,
Savings Plans, tax, support or every AWS service.

To create alerts manually, open **Billing and Cost Management → Budgets → Create
budget**, choose a monthly cost budget, and configure actual-cost notifications
with absolute USD thresholds such as **$1, $3 and $5**. Verify email/SNS delivery
and confirmation. These are user-chosen examples, not limits enforced by this
tool. Budget alerts can be delayed and **do not stop resources**. The `budget`
command lists existing budget limits/spend; it does not create alerts or audit
their recipients/delivery configuration.

## Safe lab cleanup and Terraform

`cleanup` only generates a review list. Default VPC entries are excluded; other
default-network dependencies may appear as context. Ownership and full deletion
dependencies are **unknown**, so candidates are not approved deletion targets
and the list is not a dependency-safe deletion order. Confirm account, region,
project tags, shared use, snapshots, backups and dependent resources manually.

For Terraform infrastructure, identify the exact root module, backend and
workspace used in the lab. Inspect `terraform plan` there. After reviewing
ownership/dependencies and explicitly deciding to remove it, use your normal
manual `terraform destroy` workflow. Do not delete Terraform-managed resources
through AWS APIs just because they appear in this inventory.

`terraform-check` discovers directories containing `.tf` files as **candidate**
modules, not proven root modules. It reads local version-4 `.tfstate` files,
including workspace state outside `.terraform`, but skips `.terraform`, `.git`,
`.venv` and `node_modules`. Remote state is not downloaded, state backup files
are not treated as current, and missing local state proves nothing about AWS.
Only resource type/name/module and allowlisted infrastructure `id`/`arn` fields
are emitted. Identifiers for unknown types and credential resources (such as
IAM access keys) are suppressed because IDs can be secret. An optional audit
comparison flags matching identifiers or unobserved/unsupported identifiers;
it is a possible drift lead, not proof of drift or deletion. Verify account,
region, workspace and scan coverage, then use Terraform's plan for real drift.

Stopping EC2 does not remove EBS/snapshots or retained public IPv4. Scaling ECS
services to zero does not remove load balancers, NAT gateways, ECR images or log
storage. RDS, EFS, S3, backups, endpoints and hosted zones may also remain.
Re-run inventory and check Billing later after any manual cleanup.

## Development and offline tests

```bash
python -m unittest discover -s tests -v
```

Tests use mocks and local SDK models with dummy credentials; no real AWS calls
or deletion occur. No real-account audit is run as part of development.

Architecture: `aws_session.py` owns SDK configuration/pagination;
`services/catalog.py` declares allowlisted inventory checks; `scanner.py`
orchestrates nested discovery and coverage; `resource_analyzer.py` assigns
qualitative risk; separate modules handle Billing, cleanup planning, Terraform,
reports and CLI. Extend the catalog and add mocked pagination/failure tests
when introducing new service coverage.

API references: [Boto3](https://docs.aws.amazon.com/boto3/latest/reference/index.html),
[Cost Explorer](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ce/client/get_cost_and_usage.html),
[S3 pagination](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/paginator/ListBuckets.html).
