# Звіт: ДЗ 6 — Amazon RDS PostgreSQL

Статус: НЕ ВИКОНАНО В AWS / заповнити після фактичної перевірки.

Автор: ____________________
Дата виконання: ____________________
Регіон: ____________________
Database identifier: ____________________

## 1. Створення RDS

Вставити скриншоти RDS → Databases та Configuration: статус Available, PostgreSQL, db.t3.micro, 20 GiB SSD (gp2), backup retention 7 days.

## 2. Endpoint та Connectivity

Вставити скриншот Endpoint, Publicly accessible: Yes та Security Group із TCP 5432 лише з IP /32. Пароль не показувати.

## 3. Підключення через psql

Вставити скриншот команди підключення та успішної сесії `postgres=>`.

## 4. Створення users

Вставити скриншот CREATE TABLE та фактичної відповіді.

## 5. Додавання запису

Вставити скриншот INSERT для Івана та фактичної відповіді.

## 6. Перевірка

Вставити скриншот SELECT * FROM users з рядком Іван / ivan@example.com.

## 7. Видалення

Вставити скриншот видалення/відсутності RDS після Terraform destroy. Зафіксувати перевірку snapshots, retained backups та Secrets Manager.

## Висновок

Заповнити лише за фактичними результатами; до виконання не стверджувати, що підключення або SQL перевірені.
