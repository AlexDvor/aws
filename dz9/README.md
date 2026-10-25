# DZ9 — CloudWatch для EC2

Terraform створює **новий навчальний EC2**, а не змінює наявний інстанс:

- Amazon Linux 2023, `t3.micro` (2 vCPU), detailed monitoring CPU щохвилини.
- Окремі VPC, публічна підмережа, Internet Gateway; вхідні порти закриті.
- IAM instance profile з `CloudWatchAgentServerPolicy` і `AmazonSSMManagedInstanceCore`.
- CloudWatch Agent через user data: `CWAgent / mem_used_percent`, dimension лише `InstanceId`, інтервал 60 секунд.
- Два аларми: CPU **> 80%**, пам’ять **> 75%**. Кожен перевіряє середнє за хвилину і вимагає **5 із 5 послідовних хвилин** перевищення. Відсутні дані не вважаються нормальними (`missing`).
- SNS topic, email subscription та dashboard з обома метриками.

Метрики надходять із хвилинною деталізацією та затримкою доставки, це не миттєвий real-time потік.

## Розгортання

Потрібні Terraform >= 1.6, AWS credentials для потрібного акаунта та права на EC2/VPC, IAM (включно з PassRole), SSM Parameter Store (читання AMI), CloudWatch і SNS. Облікові дані не записуйте у `.tf`.

### Підключення через ваші профілі student-base → admin

Використовуйте вже налаштовану роль `cli-admin-role`: повторно створювати IAM-користувача або AdministratorAccess для цього ДЗ не потрібно. `student-base` має лише право AssumeRole, тому запускати Terraform від нього не слід. Роль EC2, яку створює цей приклад, окрема: їй надаються політики CloudWatch Agent та SSM, а не AdministratorAccess.

Якщо профіль `admin` **без MFA**, у PowerShell перед Terraform:

```powershell
$env:AWS_PROFILE = "admin"
aws sts get-caller-identity --profile admin
```

Якщо в `admin` є `mfa_serial`, використайте AWS CLI як джерело тимчасових credentials для Terraform. Не покладайтеся на те, що Terraform сам прочитає кеш AWS CLI або запросить MFA. Додайте окремий профіль у `%USERPROFILE%\.aws\config`, зберігши наявні секції:

```ini
[profile dz9-terraform]
credential_process = aws configure export-credentials --profile admin --format process
region = eu-central-1
```

Потрібна AWS CLI v2 з командою `configure export-credentials`, а `aws` має бути в PATH. У PowerShell:

```powershell
# Приберіть можливі старі credentials лише з поточного процесу термінала.
Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY, Env:AWS_SESSION_TOKEN -ErrorAction SilentlyContinue
aws sts get-caller-identity --profile admin
# Введіть MFA-код, якщо CLI його запитає; цим також прогрівається кеш CLI.
$env:AWS_PROFILE = "dz9-terraform"
aws sts get-caller-identity
```

Перевірте, що `Arn` показує `assumed-role/cli-admin-role/...` потрібного акаунта. Команди `get-caller-identity` не показують секретних ключів. Не запускайте `export-credentials` окремо з виведенням у консоль: через `credential_process` її результат отримує Terraform. Якщо сесія закінчилася і Terraform повідомляє про credentials/MFA, повторіть `aws sts get-caller-identity --profile admin` інтерактивно, а потім повторіть потрібну команду Terraform. Перед `destroy` також потрібна чинна сесія.

Регіон у вашому гайді — `eu-central-1`, а початковий приклад DZ9 — `eu-south-2`. Для виконання ДЗ у Frankfurt вкажіть `aws_region = "eu-central-1"` у `terraform.tfvars` **перед першим plan/apply**. Саме `var.aws_region` у provider задає регіон Terraform, незалежно від регіону CLI-профілю. В AWS Console відкривайте цей самий регіон. Не змінюйте регіон уже розгорнутого прикладу без окремого плану міграції/видалення ресурсів.

У PowerShell з кореня репозиторію:

```powershell
cd dz9
Copy-Item terraform.tfvars.example terraform.tfvars
# Відредагуйте notification_email і за потреби aws_region.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=dz9.tfplan
terraform apply dz9.tfplan
```

Відкрийте лист **AWS Notification — Subscription Confirmation** та натисніть **Confirm subscription**. Terraform не може підтвердити володіння вашою поштою. До підтвердження повідомлення алармів не надходитимуть. Після підтвердження перевірте SNS → Topics → topic з `terraform output sns_topic_arn` → Subscriptions: замість `Pending confirmation` має бути підтверджена підписка (Subscription ARN).

Створення EC2 не означає завершення user data. Зачекайте декілька хвилин, оберіть той самий регіон у Console. EC2 → Instances → інстанс із `terraform output instance_id` → Connect → Session Manager → Connect. Ваша AWS identity також повинна мати права запуску SSM session. SSH-ключ не потрібний.

У сесії:

```bash
sudo cloud-init status --wait
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a status
sudo cat /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

Якщо агент не працює:

```bash
sudo tail -n 100 /var/log/cloud-init-output.log
sudo tail -n 100 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
sudo journalctl -u amazon-cloudwatch-agent --no-pager -n 50
```

Перевірте успіх `dnf`, IAM profile, доступ в інтернет і правильний регіон. За потреби після усунення причини повторіть `sudo bash /var/lib/cloud/instance/scripts/part-001`. Якщо Session Manager недоступний, перевірте IAM, SSM Agent, мережу та EC2 → Monitor and troubleshoot → Get system log.

## Метрики і тест CPU

CloudWatch → Metrics → All metrics:

1. `EC2 → Per-Instance Metrics` → потрібний `InstanceId` → `CPUUtilization`.
2. `CWAgent → InstanceId` → той самий інстанс → `mem_used_percent`.
3. Додайте обидві метрики на один графік, оберіть Average, period 1 minute, часовий діапазон останньої години. Перевірте нові точки після оновлення. Додатково доступний dashboard з `terraform output dashboard_name`.

Спочатку дочекайтеся даних і стану `OK` аларму. Підтвердьте SNS **до тесту**. У Session Manager виконайте один варіант:

```bash
sudo dnf install -y stress-ng
stress-ng --cpu 2 --timeout 600
```

Або без додаткових пакетів:

```bash
for i in 1 2; do timeout 600 yes > /dev/null & done
wait
```

Під час тесту відкрийте CloudWatch → Alarms і графік CPU. Після 5 послідовних хвилин перевищення, з урахуванням затримки доставки та оцінювання, очікуйте `ALARM` і лист від SNS. CPU-тест **не перевіряє memory alarm**. Не підміняйте тест ручним `SetAlarmState`.

Для окремої перевірки пам’яті на цьому disposable інстансі можна використати `stress-ng`:

```bash
stress-ng --vm 1 --vm-bytes 80% --vm-keep --timeout 600
```

Стежте за `free -m` та CloudWatch. Це не гарантує перевищення 75%: фактичне споживання залежить від доступної пам’яті. У разі OOM або погіршення доступу припиніть тест (`Ctrl+C`); перевірте журнали. Не запускайте цей тест на робочому сервері. Для листа потрібен фактичний перехід в `ALARM`; якщо підписку підтвердили пізно, дайте CPU охолонути до `OK` і повторіть тест.

## Скриншоти для здачі

Створіть текстовий документ і вставте **власні фактичні скриншоти** з видимими регіоном, InstanceId, параметрами та часом:

1. CloudWatch → Metrics: один графік з CPUUtilization та mem_used_percent вашого інстансу, видимі namespace й dimensions у списку метрик.
2. CloudWatch → Alarms: обидва аларми та їхні Details із порогами 80/75, `GreaterThanThreshold`, Average, period 1 minute, 5 із 5 datapoints (5 хвилин).
3. SNS → Topics → ваш topic: назва/ARN, ваша email-адреса та підтверджена subscription.
4. CloudWatch → Alarms: CPU alarm у `ALARM` після навантаження; бажано також History з переходом стану.
5. Пошта: отриманий лист про `ALARM`, назва аларму та час (окремо від листа підтвердження).
6. CloudWatch → Metrics → CPUUtilization: зростання CPU під час 10-хвилинного тесту.
7. Якщо потрібне видалення: після destroy — списки Alarms та SNS Topics із фільтром за збереженими назвами й відсутніми ресурсами.

Цей репозиторій не містить доказів розгортання, отриманих листів або скриншотів. Їх потрібно отримати у вашому AWS акаунті; Terraform validate цього не підтверджує.

## Вартість і видалення

Ресурси можуть бути платними: EC2/EBS, публічна IPv4, detailed monitoring, custom metric, alarms, dashboard, SNS. `t3.micro` може нараховувати додаткову оплату за CPU credits під тривалим навантаженням. Не припускайте покриття Free Tier.

Після збереження доказів збережіть назви алармів і topic, потім видаліть **усі ресурси цього прикладу**:

```powershell
terraform output
terraform plan -destroy
terraform destroy
```

Підтвердьте видалення, перевірте Console і зробіть останній скриншот. Не видаляйте ресурси вручну перед destroy без потреби. State містить email та ідентифікатори ресурсів: не публікуйте state, plan або приватний tfvars.

## Джерела

- [AWS: встановлення CloudWatch Agent](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html)
- [AWS: конфігурація агента, mem та append_dimensions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html)
- [Terraform: CloudWatch metric alarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm.html)
- [AWS CLI: export-credentials для credential_process](https://docs.aws.amazon.com/cli/latest/reference/configure/export-credentials.html)
