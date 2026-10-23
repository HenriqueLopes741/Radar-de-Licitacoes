import pandas as pd 

COLUNAS = [
    "numero_controle_pncp",
    "orgao",
    "uf",
    "municipio",
    "objeto",
    "modalidade",
    "data_publicacao",
    "data_encerramento",
    "valor_estimado",
    "valor_homologado",
    "situacao",
    "ano_compra",
    "link_pncp",
]

CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS contratacoes (
    numero_controle_pncp TEXT PRIMARY KEY,
    orgao                TEXT,
    uf                   CHAR(2),
    municipio            TEXT,
    objeto               TEXT,
    modalidade           TEXT,
    data_publicacao      TIMESTAMP,
    data_encerramento    TIMESTAMP,
    valor_estimado       NUMERIC(18, 2),
    valor_homologado     NUMERIC(18, 2),
    situacao             TEXT,
    ano_compra           INTEGER,
    link_pncp            TEXT,
    atualizado_em        TIMESTAMP DEFAULT now()
)
"""

INSERIR = f"""
INSERT INTO contratacoes ({",".join(COLUNAS)}) 
VALUES ({",".join(["%s"] * len(COLUNAS))})
"""

def carregar_dados(arquivo_csv, conexao): 
    df = pd.read_csv(arquivo_csv, encoding="utf-8-sig")

    # Tipos do Python (e não do numpy), que o driver do Postgres sabe converter
    linhas = df[COLUNAS].astype(object).values.tolist()

    with conexao.cursor() as cursor: 
        cursor.execute(CRIAR_TABELA)
        cursor.executemany(INSERIR, linhas)

    conexao.commit()
