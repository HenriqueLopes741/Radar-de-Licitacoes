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


def filtrar_contratacoes(
    conexao,
    uf=None,
    municipio=None,
    orgao=None,
    palavra_chave=None,
    valor_min=None,
    valor_max=None,
    encerra_de=None,
    encerra_ate=None,
):
    # Cada filtro informado vira uma condição. Os valores vão como parâmetros,
    # nunca colados no SQL, porque parte deles vem do que o usuário digita
    condicoes = []
    valores = []

    if uf:
        condicoes.append("uf = %s")
        valores.append(uf)

    if palavra_chave:
        condicoes.append("objeto ILIKE %s")
        valores.append(f"%{palavra_chave}%")

    if orgao:
        condicoes.append("orgao ILIKE %s")
        valores.append(f"%{orgao}%")

    if municipio:
        condicoes.append("municipio = %s")
        valores.append(municipio)

    # Números e datas comparados com None: zero é um limite válido
    if valor_min is not None:
        condicoes.append("valor_estimado >= %s")
        valores.append(valor_min)

    if valor_max is not None:
        condicoes.append("valor_estimado <= %s")
        valores.append(valor_max)

    # Só a parte da data: "até dia 15" inclui o que encerra às 9h do dia 15
    if encerra_de is not None:
        condicoes.append("data_encerramento::date >= %s")
        valores.append(encerra_de)

    if encerra_ate is not None:
        condicoes.append("data_encerramento::date <= %s")
        valores.append(encerra_ate)

    sql ="SELECT * FROM contratacoes"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY data_publicacao DESC"

    with conexao.cursor() as cursor:
        cursor.execute(sql, valores)
        colunas = [coluna.name for coluna in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=colunas)

def _resumir(df, chave):
    # Decimal (NUMERIC do banco) vira float, que os gráficos sabem desenhar
    return (
        df.assign(valor_estimado=df["valor_estimado"].astype(float))
        .groupby(chave)
        .agg(
            quantidade=("numero_controle_pncp", "size"),
            valor_total=("valor_estimado", "sum"),
        )
        .reset_index()
    )


def resumo_por_dia(df):
    # to_datetime porque, sem linhas, a coluna não chega com tipo de data
    dias = pd.to_datetime(df["data_publicacao"]).dt.date
    return _resumir(df.assign(dia=dias), "dia")


def resumo_por_uf(df):
    return _resumir(df, "uf")

def listar_ufs(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT uf FROM contratacoes WHERE uf IS NOT NULL ORDER BY uf"
        )
        return [uf for (uf,) in cursor.fetchall()]


def listar_municipios(conexao, uf):
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT municipio FROM contratacoes"
            " WHERE uf = %s AND municipio IS NOT NULL ORDER BY municipio",
            [uf],
        )
        return [municipio for (municipio,) in cursor.fetchall()]

def periodo_publicado(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT MIN(data_publicacao)::date, MAX(data_publicacao)::date"
            " FROM contratacoes"
        )
        return cursor.fetchone()


def _dias_para_encerrar(df, hoje):
    encerramento = pd.to_datetime(df["data_encerramento"]).dt.normalize()
    return (encerramento - pd.Timestamp(hoje)).dt.days


def indicadores(df, hoje):
    valores = df["valor_estimado"].astype(float)
    # Valor zero é orçamento sigiloso, não "custa nada": fica fora da mediana
    divulgados = valores[valores > 0]
    return {
        "contratacoes": len(df),
        "abertas": int((_dias_para_encerrar(df, hoje) >= 0).sum()),
        "mediana_valor": divulgados.median() if not divulgados.empty else None,
        "fatia_sem_valor": 1 - len(divulgados) / len(df) if len(df) else 0.0,
    }


def com_dias_para_encerrar(df, hoje):
    return df.assign(encerra_em=_dias_para_encerrar(df, hoje))

def tem_dados(conexao):
    # Num ambiente novo a tabela só existe depois da primeira carga da DAG
    with conexao.cursor() as cursor:
        cursor.execute("SELECT to_regclass('contratacoes') IS NOT NULL")
        return cursor.fetchone()[0]
