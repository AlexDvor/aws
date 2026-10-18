# AWS learning projects

- [AWS Cost Guard](aws-cost-guard/README.md): read-only AWS resource inventory,
  post-lab cost-risk checklist, audit reports and optional Billing queries.
- [EC2 / Terraform lab](dz3/Readme.md): infrastructure lab and its instructions.

## Check for resources left after a lab

Run in Windows Git Bash from this repository:

```bash
cd aws-cost-guard
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py scan --profile admin --all-regions
```

See the [full setup, MFA, troubleshooting and command guide](aws-cost-guard/README.md)
if environment creation or pip fails. Scans do not stop/delete resources and do
not call Cost Explorer. No findings never proves zero AWS costs.

Local keys, Terraform State, variable files, environments and generated audit
reports must stay out of Git. Do not publish console output containing your
account ID, caller ARN or infrastructure identifiers.
