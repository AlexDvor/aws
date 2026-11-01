# ДЗ10 — Elastic Beanstalk через Terraform

Створюються `my-app`, Web server environment `my-app-env`, Python Sample application, один `t3.micro`, service role та EC2 instance profile з `AWSElasticBeanstalkWebTier`. У режимі `SingleInstance` Min/Max/Desired дорівнюють 1; балансувальник і scaling triggers не створюються. Увімкнено enhanced health reporting.

## Запуск

Потрібні AWS credentials з правами на Elastic Beanstalk, IAM/PassRole та створення його EC2/CloudFormation ресурсів. Використовуйте налаштований AWS-профіль. Конфігурація використовує **default VPC** регіону `eu-central-1`; він повинен мати публічні підмережі з доступом до Internet Gateway. Інший регіон задається через `-var="aws_region=..."` під час plan.

Якщо роль або instance profile `aws-elasticbeanstalk-ec2-role` вже існують, спочатку імпортуйте їх у відповідні ресурси Terraform, а не створюйте повторно.

```powershell
cd dz10
# За потреби: $env:AWS_PROFILE = "ваш-профіль"
aws sts get-caller-identity
terraform init
terraform fmt -check
terraform validate
terraform plan -out=dz10.tfplan
terraform apply dz10.tfplan
terraform output -raw application_url
```

Вибирається найновіший доступний AWS stack Python 3.13 на Amazon Linux 2023. Перед apply звірте output `platform` у plan з рекомендованою версією в AWS Console. Дочекайтеся стану середовища `Ready`, health `Ok` та перевірте Events на помилки. Відкрийте URL з output і перевірте Sample application.

## Скриншоти для здачі

Створіть текстовий документ **`ДЗ9_ПІБ`** — саме таку назву вказано в умові, попри папку `dz10`. Вставте фактичні скриншоти з короткими підписами:

1. Elastic Beanstalk → Applications: `my-app` і його середовище `my-app-env`.
2. Configuration → Instance traffic and scaling: `Instance types: t3.micro`.
3. Monitoring: `CPUUtilization`, `NetworkIn`, `NetworkOut`, `Environment health`. За потреби додайте відповідні графіки через налаштування Monitoring і дочекайтеся даних.
4. Configuration → Instance traffic and scaling: `Environment type: Single instance`. Для перевірки Min/Max/Desired відкрийте пов'язану EC2 Auto Scaling group: усі три значення мають бути 1.
5. Згенерований URL у браузері: тестова сторінка з видимою адресою.

Прикріпіть документ і посилання на нього в LMS. Terraform-файли та `validate` не замінюють скриншоти фактичного розгортання.

Після здачі видаліть ресурси цього завдання:

```powershell
terraform destroy
```

EC2/EBS та публічна IPv4 можуть тарифікуватися; покриття Free Tier залежить від акаунта.

Джерела: [AWS CreateEnvironment — Sample application за відсутності VersionLabel](https://docs.aws.amazon.com/elasticbeanstalk/latest/api/API_CreateEnvironment.html), [Single instance](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features-managing-env-types.html), [параметри середовища](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html).
