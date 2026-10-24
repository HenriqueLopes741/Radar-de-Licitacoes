import os

import psycopg2
import pytest

URL_BANCO_TESTE = os.environ.get(
    "PNCP_TESTE_DB_URL",
    "postgresql://airflow:airflow@localhost:5433/pncp_teste",
)


@pytest.fixture
def conexao():
    # Banco de testes real: o upsert é comportamento do Postgres, um mock não o provaria
    try:
        conn = psycopg2.connect(URL_BANCO_TESTE, connect_timeout=3)
    except psycopg2.OperationalError:
        pytest.skip("Banco de testes indisponível (suba o Docker Compose)")

    # Cada teste começa com a tabela vazia
    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS contratacoes")
    conn.commit()

    yield conn

    conn.close()
