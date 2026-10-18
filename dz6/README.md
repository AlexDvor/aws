# ДЗ 6 — Amazon RDS PostgreSQL через Terraform

Terraform створює RDS PostgreSQL `db.t3.micro`, 20 GiB General Purpose SSD (`gp2`), Single-AZ, автоматичні резервні копії на 1 день, DB subnet group та окрему Security Group. Використовуються наявні default VPC і default subnets. Public access увімкнено, TCP 5432 доступний лише з заданої IPv4 `/32`. Master username: `postgres`; пароль створює та керує ним RDS через Secrets Manager. Terraform не отримує значення пароля.

Умова ДЗ вимагає backup retention 7 днів. Поточне значення 1 день використано після відмови AWS Free plan створити instance з retention 7 днів. Це відхилення потрібно погодити з ментором; відповідність вимозі 7 днів не підтверджена.

Уточнення до умови: `db.t3.micro` має **2 vCPU і 1 GiB RAM**, а не 1 vCPU. Тип інстансу залишено відповідно до завдання.

## 1. Підготовка

Потрібні Terraform >= 1.6, AWS CLI, налаштований AWS-профіль із правами на RDS, EC2 networking та керування RDS master secret, PostgreSQL client `psql`. AWS CLI і Terraform не встановлюють `psql` автоматично. Після встановлення PostgreSQL client додайте його `bin` до PATH і перевірте `psql --version`.

Команди нижче — для PowerShell, із кореня репозиторію:

```powershell
cd dz6
$env:AWS_PROFILE = "admin" # Замініть на свій профіль; для default цей рядок не потрібен.
aws sts get-caller-identity
Copy-Item terraform.tfvars.example terraform.tfvars
```

Відредагуйте `terraform.tfvars`: регіон, унікальний identifier та **вашу фактичну публічну IPv4/32**. `203.0.113.10` — лише приклад, з ним підключення не працюватиме. Після зміни IP/VPN оновіть CIDR і повторіть plan/apply. Не записуйте AWS keys або пароль БД у цей файл.

Перевірте в AWS Console, що у вибраному регіоні є default VPC, default subnets щонайменше у двох AZ, DNS resolution/hostnames та маршрут `0.0.0.0/0` до Internet Gateway для кожної вибраної subnet. Змінені Network ACL мають пропускати з'єднання та зворотний трафік. Terraform перевіряє наявність subnet і DNS, але не відновлює змінену default network. Якщо default VPC відсутня, спершу відновіть її через VPC Console або оберіть регіон, де вона є.

**Витрати:** Terraform не має перемикача Console «Free Tier». Право на Free Tier залежить від акаунта, дати реєстрації та чинних умов AWS. Перед apply перевірте Billing → Free Tier і ціни у своєму регіоні. Secrets Manager, public IPv4, backup понад включені обсяги та інші ресурси можуть тарифікуватися окремо. Ця конфігурація не гарантує нульових витрат.

## 2. Створення

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan -out=dz6.tfplan
terraform apply dz6.tfplan
terraform output
```

Перегляньте plan перед apply. Очікується створення лише RDS instance, DB subnet group, Security Group та ingress rule. Default VPC не створюється і не видаляється. Обрана версія PostgreSQL — регіональний default RDS; якщо він несумісний із класом або потрібна фіксована версія, перевірте доступні пропозиції й задайте `engine_version` перед apply:

```powershell
aws rds describe-orderable-db-instance-options --engine postgres --db-instance-class db.t3.micro --region eu-central-1 --query "OrderableDBInstanceOptions[].EngineVersion" --output text
```

Дочекайтеся статусу `Available`. У Console відкрийте RDS → Databases → ваш identifier. Зробіть скриншоти параметрів і Endpoint. `db_host` — адреса без порту, `db_endpoint` — адреса з `:5432`.

## 3. Пароль та підключення

У деталях RDS знайдіть Master credentials ARN → відкрийте secret у Secrets Manager → Retrieve secret value. Альтернатива для пошуку secret: `terraform output -raw master_secret_arn`. Скопіюйте пароль приватно; не робіть скриншот secret і не виводьте його в термінал чи звіт.

```powershell
$dbHost = terraform output -raw db_host
$env:PGSSLMODE = "require"
$env:PGCLIENTENCODING = "UTF8"
psql -h $dbHost -U postgres -d postgres -W
```

Введіть пароль у прихованому prompt. Має з'явитися prompt `postgres=>`; зробіть скриншот успішного підключення. `sslmode=require` вмикає TLS; для перевірки імені сервера та CA можна налаштувати `verify-full` з офіційним RDS CA bundle.

Для помилки timeout перевірте фактичну IP `/32`, статус Available, Publicly accessible, Security Group, IGW routes, NACL і локальний firewall. Для authentication failed перевірте актуальний secret та username `postgres`.

## 4. SQL та скриншоти

У відкритій сесії `psql` виконуйте команди **окремо**, роблячи скриншот після кожної:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE
);
```

Очікувана відповідь: `CREATE TABLE`.

```sql
INSERT INTO users (name, email) VALUES ('Іван', 'ivan@example.com');
```

Очікувана відповідь: `INSERT 0 1`.

```sql
SELECT * FROM users;
```

У результаті перевірте `Іван | ivan@example.com`. Завершення сесії: `\q`.

Альтернатива для одного запуску з PowerShell:

```powershell
psql -h $dbHost -U postgres -d postgres -W -f users.sql
```

`users.sql` призначений для порожньої навчальної БД; повторний запуск зупиниться на наявній таблиці. Не запускайте його після ручного створення таблиці. Очікувані відповіді вище не є доказом виконання — додавайте лише фактичні результати.

## 5. Звіт для ментора

Заповніть [REPORT_TEMPLATE.md](REPORT_TEMPLATE.md), вставте реальні скриншоти у текстовий документ Word/Google Docs або експортуйте заповнений Markdown у PDF. Локальні зображення можна тримати в `evidence/` (папка виключена з Git). У фінальному документі зображення мають бути вбудовані та читабельні.

Потрібні зображення: створений instance; PostgreSQL / db.t3.micro / 20 GiB SSD; Endpoint; успішний psql; CREATE TABLE; INSERT; SELECT з Іваном; видалення за потреби. Якщо параметри не вміщаються на одному екрані, додайте окремі скриншоти Configuration і Connectivity & security. Зафіксуйте backup retention 7 days та доступ лише зі своєї IP. Приховайте credentials, account ID та зайві персональні дані, залишивши перевірювані параметри й Endpoint видимими.

## 6. Видалення після збереження доказів

**Destroy безповоротно видаляє навчальні дані; final snapshot не створюється, automated backups видаляються.** Спочатку збережіть скриншоти та потрібні дані. Виконуйте з `dz6` у тому самому AWS-профілі:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
terraform state list
```

Перегляньте план видалення перед apply. Після успіху `terraform state list` має бути порожнім; у RDS Console перевірте видалення instance та збережіть скриншот. Парольний secret керується RDS; перевірте також Secrets Manager, RDS snapshots і retained automated backups на залишені платні ресурси. Ресурси з інших домашніх завдань не видаляються.

Не видаляйте локальний state до завершення destroy. `.terraform.lock.hcl` слід зберігати у Git; state, tfvars і plan-файли — ні.

## Офіційні джерела

- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [RDS у VPC та public connectivity](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html)
- [Актуальні умови RDS Free Tier](https://aws.amazon.com/rds/free/)
- [Характеристики класів RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.Summary.html)
