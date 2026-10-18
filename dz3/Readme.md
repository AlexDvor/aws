# AWS лабораторна: EC2, nginx та Application Load Balancer

Проєкт створює окрему VPC, дві public subnet у різних Availability Zones, два EC2 `t3.micro` з Amazon Linux 2023, AWS Key Pair, Security Groups, Target Group та Application Load Balancer з HTTP listener. nginx встановлюється автоматично через `user_data`, або вручну за вашим вибором.

**Файли підготовлено без запуску Terraform та без створення AWS-ресурсів. Конфігурація ще не перевірена через `terraform validate` чи фактичне розгортання.**

## Безпека й витрати

- HTTP до ALB та безпосередньо EC2 дозволений лише з вашого CIDR, рекомендовано публічний IPv4 `/32`.
- SSH дозволений лише через сервіс EC2 Instance Connect відповідного регіону. SSH з локального комп'ютера цими правилами не дозволений.
- Приватний ключ генерується локально й не потрапляє у Terraform state. Диски зашифровані, IMDSv2 обов'язковий. EC2 не отримують IAM role.
- NAT Gateway та Elastic IP не створюються; CPU credits встановлені в `standard`, щоб уникнути доплат за surplus credits.
- EC2, EBS, ALB, public IPv4 та трафік можуть бути платними. Безкоштовність Free Tier не гарантується.
- **Stop EC2 не припиняє всі витрати: ALB та EBS залишаються. Для завершення лабораторної використовуйте `terraform destroy`. Автоматичного видалення за таймером немає.**
- Це навчальний HTTP без TLS: не передавайте паролі або приватні дані.

## Одноразова підготовка

Усі команди нижче виконуйте самостійно у PowerShell з папки проєкту. Потрібні Terraform, AWS CLI, OpenSSH та AWS identity з дозволами створювати й видаляти ресурси лабораторної. Для браузерного SSH потрібні також IAM permissions EC2 Instance Connect. Не використовуйте root account і не записуйте AWS credentials у файли проєкту.

Налаштуйте вашу навчальну AWS identity. Якщо доступний IAM Identity Center:

```powershell
aws configure sso
$env:AWS_PROFILE = "your-profile"
aws sso login --profile $env:AWS_PROFILE
aws sts get-caller-identity
```

Якщо credentials уже налаштовані, виберіть відповідний profile. Перевірте Account та ARN перед створенням ресурсів.

Створіть пару ключів і задайте passphrase на запит. Не перезаписуйте наявний ключ:

```powershell
New-Item -ItemType Directory -Path .keys -Force
ssh-keygen -t rsa -b 4096 -m PEM -f .keys/nginx-lab
Copy-Item terraform.tfvars.example terraform.tfvars
```

Приватний ключ: `.keys/nginx-lab`; публічний: `.keys/nginx-lab.pub`. Збережіть приватний ключ у захищеному місці. Terraform реєструє лише публічний ключ як нову AWS Key Pair. Браузерний Instance Connect використовує тимчасовий ключ; завантажувати приватний файл у браузер не потрібно.

У `terraform.tfvars` замініть `203.0.113.10/32` на **ваш справжній публічний IPv4/32**, оберіть регіон. При зміні IP або VPN змініть CIDR і повторно застосуйте конфігурацію. Для особистого виконання команд nginx встановіть `install_nginx_automatically = false` перед створенням EC2.

```powershell
terraform init
terraform fmt
terraform validate
terraform plan
```

## Створення однією командою

Після одноразової підготовки:

```powershell
terraform apply
```

Перегляньте план та підтвердьте `yes`. При помилці apply частина ресурсів могла вже створитися: виправте помилку або виконайте destroy.

## Виконання завдання

1. У тому самому регіоні AWS Console відкрийте EC2 → Instances, знайдіть `nginx-lab-web-1` і `nginx-lab-web-2`.
2. На кожному виберіть Connect → EC2 Instance Connect, public IP та користувача `ec2-user`.
3. При ручному встановленні виконайте на **обох** інстансах:

```bash
sudo yum install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

При автоматичному встановленні перевірте завершення cloud-init та nginx:

```bash
sudo cloud-init status --wait
sudo systemctl status nginx
```

4. Отримайте прямі адреси EC2 і відкрийте їх з дозволеної IP:

```powershell
terraform output instances
```

5. В EC2 → Target Groups дочекайтеся **двох Healthy targets**. Після apply встановлення nginx і health checks можуть зайняти кілька хвилин. При ручному встановленні targets залишатимуться unhealthy до запуску nginx.
6. Отримайте адресу ALB:

```powershell
terraform output -raw alb_url
```

Відкрийте URL з явним `http://` та збережіть скриншот стандартної сторінки nginx з адресним рядком. Сторінка підтверджує відповідь ALB; працездатність обох targets перевіряйте окремо. Стандартна сторінка nginx не змінюється.

При HTTP 503 перевірте targets і nginx. При timeout перевірте свій CIDR та VPN. При помилці браузерного SSH перевірте IAM permissions, регіон, public IP і статус EC2.

## Повне видалення однією командою

Після скриншота, у тій самій папці та з тим самим AWS profile:

```powershell
terraform destroy
```

Перегляньте перелік та введіть `yes`. Terraform видаляє керовані цим state EC2, їхні root EBS volumes, ALB, listener, Target Group, AWS Key Pair, Security Groups та мережу лабораторної. Локальна пара ключів залишається.

Перевірте в AWS Console, що EC2 terminated, ALB та диски видалені. Якщо destroy завершується помилкою, усуньте причину й повторіть його: залишені ресурси можуть коштувати грошей. Створені вручну ресурси поза Terraform ця команда не видаляє. Нараховані раніше витрати залишаються, billing оновлюється із затримкою.

**Не видаляйте state, налаштування або проєкт до завершення cleanup. `terraform state rm` не видаляє AWS-ресурси.** Якщо викладач вимагає Stop у консолі, виконайте його після скриншота, а потім все одно виконайте destroy. Новий apply може відновити ресурси та витрати.

Ключі, state, plan та `terraform.tfvars` виключені з Git через `.gitignore`; захищайте локальні файли правами доступу. Після init додайте `.terraform.lock.hcl` у Git для фіксації провайдера.

Офіційні джерела: [EC2 Instance Connect](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-prerequisites.html), [Amazon Linux 2023](https://docs.aws.amazon.com/linux/al2023/ug/ec2.html), [вартість ALB](https://aws.amazon.com/elasticloadbalancing/pricing/), [public IPv4](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-instance-addressing.html).

## Основні команди Terraform

Цей проєкт призначений для вивчення хмарних обчислень з AWS і Terraform.

Виконуйте команди в терміналі з папки проєкту.

| Команда | Призначення |
|---|---|
| `terraform version` | Показує встановлену версію Terraform. |
| `terraform init` | Ініціалізує проєкт і завантажує потрібні провайдери. |
| `terraform fmt` | Форматує файли конфігурації `.tf`. |
| `terraform validate` | Перевіряє коректність конфігурації. |
| `terraform plan` | Показує заплановані зміни ресурсів. |
| `terraform apply` | Створює або змінює ресурси після підтвердження. |
| `terraform show` | Показує поточний стан ресурсів або збережений план. |
| `terraform output` | Показує значення, визначені в блоках `output`. |
| `terraform destroy` | Видаляє ресурси, якими керує конфігурація, після підтвердження. |

## Звичайна послідовність роботи

Спочатку створіть конфігурацію ресурсів у файлі `main.tf`, потім виконайте:

```powershell
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
```

У порожньому проєкті Terraform ще не має опису ресурсів для створення.

## Видалення навчальних ресурсів

```powershell
terraform destroy
```

Перед підтвердженням перевірте перелік ресурсів, які буде видалено.

**Увага:** `terraform apply` може створити платні ресурси AWS. Перед підтвердженням уважно переглядайте план змін і вартість вибраних ресурсів.
