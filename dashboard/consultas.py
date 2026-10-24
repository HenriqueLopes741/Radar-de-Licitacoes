import os

import pandas as pd
import psycopg2


def conectar():
    # No Docker o endereço vem do docker-compose; fora dele, a porta exposta na máquina
    url = os.environ.get(
        "PNCP_DB_URL",
        "postgresql://airflow:airflow@localhost:5433/pncp",
    )
    return psycopg2.connect(url)


def filtrar_contratacoes(conexao, uf=None):
    # Cada filtro informado vira uma condição. Os valores vão como parâmetros,
    # nunca colados no SQL, porque parte deles vem do que o usuário digita
    condicoes = []
    valores = []

    if uf:
        condicoes.append("uf = %s")
        valores.append(uf)

    sql = "SELECT * FROM contratacoes"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY data_publicacao DESC"

    with conexao.cursor() as cursor:
        cursor.execute(sql, valores)
        colunas = [coluna.name for coluna in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=colunas)
