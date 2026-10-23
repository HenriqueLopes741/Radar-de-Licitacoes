-- Banco dos dados do pipeline, separado do banco interno do Airflow.
-- Só roda quando o volume do Postgres é criado pela primeira vez.
CREATE DATABASE pncp;

-- Banco usado só pelos testes (o pytest apaga e recria as tabelas nele)
CREATE DATABASE pncp_teste;
