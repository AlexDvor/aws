# ДЗ 7 — приватний S3 та CloudFront через Terraform

S3 створюється в **eu-south-2 (Spain)**. CloudFront — глобальний сервіс, його edge locations не обмежуються цим регіоном.

Конфігурація створює:

- S3-бакет з автоматично сформованою унікальною назвою та всіма чотирма налаштуваннями Block Public Access; ACL вимкнені через BucketOwnerEnforced.
- Об'єкт `example.txt` із локального файла `files/example.txt`.
- CloudFront Distribution з S3 REST origin, OAC (`always`, `sigv4`) та стандартним сертифікатом для домену `*.cloudfront.net`.
- Bucket policy з `s3:GetObject` для `cloudfront.amazonaws.com`, обмежену ARN саме цієї Distribution.
- Behavior: **Redirect HTTP to HTTPS**, **GET, HEAD**, **CachingOptimized**.

Використовується стандартна Distribution без підписки на flat-rate plan (pay as you go), без AWS WAF. Кроки майстра Console замінені декларативними ресурсами Terraform; OAC та bucket policy створюються явно. Файли через CloudFront доступні публічно; прямий анонімний доступ до S3 закритий. IAM-доступ власника для керування бакетом зберігається.

## Перед запуском

Потрібні Terraform >= 1.6 та налаштовані AWS credentials із правами керування S3, CloudFront, OAC і bucket policy. AWS CLI потрібен для команд перевірки нижче. Не записуйте ключі у Terraform-файли.

Переконайтеся, що регіон `eu-south-2` активований для акаунта: AWS Account → AWS Regions. Для цього opt-in регіону за потреби дочекайтеся завершення активації. S3 та CloudFront можуть створювати витрати; нульова вартість не гарантується.

## Створення

PowerShell, із кореня репозиторію:

```powershell
cd dz7
$env:AWS_PROFILE = "admin" # Замініть на свій профіль; для default пропустіть.
aws sts get-caller-identity
terraform init
terraform fmt -check
terraform validate
terraform plan -out=dz7.tfplan
terraform apply dz7.tfplan
terraform output
```

Перед `apply` перегляньте план. Terraform чекає розгортання CloudFront; це може тривати кілька хвилин. Bucket policy додається після створення Distribution. URL перевіряйте після успішного завершення всього `apply`.

## Перевірка

```powershell
$fileUrl = terraform output -raw file_url
Start-Process $fileUrl
curl.exe -I $fileUrl
curl.exe -I ($fileUrl -replace '^https:', 'http:')
curl.exe -I (terraform output -raw s3_file_url)
```

Очікується: HTTPS через CloudFront — `200` і вміст `example.txt`; HTTP — перенаправлення на HTTPS; прямий анонімний S3 URL — `403 AccessDenied`. Це очікувані результати, а не підтвердження фактичного розгортання.

У Console перевірте S3 → ваш бакет → Permissions → Block all public access; CloudFront → ваша Distribution → статус `Deployed`, Origins → OAC, Behaviors → три параметри із завдання. Назва в tags: `dz7-s3-cloudfront`, опис: `DZ7 private S3 with OAC`. Збережіть скриншоти цих налаштувань та відкритого файла для звіту.

Локальний `files/example.txt` можна змінити та повторити plan/apply. Через CachingOptimized попередня версія може залишатися в кеші. Для негайного оновлення після apply:

```powershell
$distributionId = terraform output -raw distribution_id
aws cloudfront create-invalidation --distribution-id $distributionId --paths "/example.txt"
```

Дочекайтеся завершення invalidation; такі запити можуть тарифікуватися за умовами AWS.

## Видалення

Після збереження результатів, із `dz7`, у тому самому AWS-профілі:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
terraform state list
```

Перегляньте план видалення перед apply. Provider вимикає CloudFront і видаляє Distribution; OAC, об'єкт та бакет також видаляються. Це може тривати кілька хвилин. `force_destroy = true` дозволяє очистити бакет, включно з додатково завантаженими файлами: **усі його об'єкти будуть безповоротно видалені**. Використовуйте бакет лише для цього ДЗ.

Після успішного destroy список state має бути порожнім; перевірте відсутність ресурсів у Console. Не видаляйте state до завершення очищення. Зберігайте `.terraform.lock.hcl` у Git; state, plan та credentials не комітьте.

## Офіційні джерела

- [Terraform: CloudFront Distribution](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudfront_distribution)
- [AWS: приватний S3 origin та OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
