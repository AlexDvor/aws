\set ON_ERROR_STOP on
\encoding UTF8

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE
);

INSERT INTO users (name, email) VALUES ('Іван', 'ivan@example.com');

SELECT * FROM users;
