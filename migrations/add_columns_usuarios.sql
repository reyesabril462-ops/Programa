-- Migration: add role-specific columns to usuarios
ALTER TABLE usuarios
  ADD COLUMN grupo VARCHAR(50) NULL,
  ADD COLUMN semestre VARCHAR(10) NULL,
  ADD COLUMN materia VARCHAR(200) NULL;

-- Note: run this SQL against your MySQL database before testing the updated registration form.
-- Example (in MySQL shell):
-- USE proyecto;
-- SOURCE path/to/migrations/add_columns_usuarios.sql;
