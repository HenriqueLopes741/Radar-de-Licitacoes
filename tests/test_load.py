import os

import pandas as pd
import psycopg2
import pytest

from src import load

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

def linha(**campos): 
    # Linha no formato do csv gerado 
    base = {
        "numero_controle_pncp": "00000000000100-1-000001/2026",
        "orgao": "PREFEITURA DE TESTE", 
        "uf": "SP",
        "municipio": "São Paulo",
        "objeto": "Aquisição de medicamentos",
        "modalidade": "Pregão - Eletrônico", 
        "data_publicacao": "2026-10-01 08:30:00",
        "data_encerramento": "2026-10-15 09:00:00",
        "valor_estimado": 1500.5,
        "valor_homologado": 1400.0,
        "situacao": "Divulgada no PNCP",
        "ano_compra": 2026, 
        "link_pncp": "https://pncp.gov.br/app/editais/00000000000100/2026/1",
    }
    base.update(campos)
    return base

def escrever_csv(pasta, linhas): 
    arquivo = pasta / "contratacoes.csv"
    pd.DataFrame(linhas).to_csv(arquivo, index=False, encoding="utf-8-sig")
    return arquivo

def consultar(conexao, sql):
    with conexao.cursor() as cursor: 
        cursor.execute(sql)
        return cursor.fetchall()

def test_carrega_as_contratacoes_do_csv(conexao, tmp_path): 
    csv = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A"),
        linha(numero_controle_pncp="B"),
    ])

    load.carregar_dados(csv, conexao)

    assert consultar(
        conexao, 
        "SELECT numero_controle_pncp FROM contratacoes ORDER BY 1",
    ) == [("A",), ("B",)]

def test_carregar_o_mesmo_csv_duas_vezes_nao_duplica(conexao, tmp_path):
    csv = escrever_csv(tmp_path, [linha(numero_controle_pncp="A")])

    load.carregar_dados(csv, conexao)
    load.carregar_dados(csv, conexao)

    assert consultar(conexao, "SELECT count(*) FROM contratacoes") == [(1,)]

def test_atualiza_a_contratacao_que_mudou(conexao, tmp_path):
    antes = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A", situacao="Divulgada no PNCP"),
    ])
    load.carregar_dados(antes, conexao)

    depois = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A", situacao="Homologada"),
    ])
    load.carregar_dados(depois, conexao)

    assert consultar(conexao, "SELECT situacao FROM contratacoes") == [
        ("Homologada",),
    ]

def test_campos_vazios_viram_nulos(conexao, tmp_path):
    csv = escrever_csv(tmp_path, [
        linha(valor_homologado=None, data_encerramento=None),
    ])

    load.carregar_dados(csv, conexao)

    assert consultar(
        conexao,
        "SELECT valor_homologado IS NULL, data_encerramento IS NULL"
        " FROM contratacoes",
    ) == [(True, True)]
