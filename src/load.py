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

# Os filtros mais comuns do dashboard e dos alertas: período e estado
CRIAR_INDICES = """
CREATE INDEX IF NOT EXISTS idx_contratacoes_data_publicacao
    ON contratacoes (data_publicacao);
CREATE INDEX IF NOT EXISTS idx_contratacoes_uf
    ON contratacoes (uf);
"""

# No reprocessamento, a linha existente recebe os dados mais recentes
ATUALIZAR = ",\n    ".join(
    f"{coluna} = EXCLUDED.{coluna}"
    for coluna in COLUNAS
    if coluna != "numero_controle_pncp"
)

INSERIR = f"""
INSERT INTO contratacoes ({", ".join(COLUNAS)})
VALUES ({", ".join(["%s"] * len(COLUNAS))})
ON CONFLICT (numero_controle_pncp) DO UPDATE SET
    {ATUALIZAR},
    atualizado_em = now()
"""

def carregar_dados(arquivo_csv, conexao): 
    df = pd.read_csv(arquivo_csv, encoding="utf-8-sig")

    # Tipos do Python (e não do numpy), que o driver do Postgres sabe converter
    df = df[COLUNAS].astype(object)

    # Vazios do CSV chegam como NaN; no banco devem ser NULL
    linhas = df.where(df.notna(), None).values.tolist()


    with conexao.cursor() as cursor: 
        cursor.execute(CRIAR_TABELA)
        cursor.execute(CRIAR_INDICES)
        cursor.executemany(INSERIR, linhas)

    conexao.commit()
