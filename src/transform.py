import json
from pathlib import Path

import pandas as pd

from src.extract import PARAMS, caminho_arquivo_bruto


ARQUIVO_ENTRADA = caminho_arquivo_bruto(
    PARAMS["dataInicial"],
    PARAMS["dataFinal"],
    PARAMS["codigoModalidadeContratacao"],
)
ARQUIVO_SAIDA = Path("data/processed/contratacoes.csv")


def transformar_dados(arquivo_entrada=None, arquivo_saida=None):
    arquivo_entrada = Path(arquivo_entrada or ARQUIVO_ENTRADA)
    arquivo_saida = Path(arquivo_saida or ARQUIVO_SAIDA)

    # 1. Verificar se o arquivo bruto existe
    if not arquivo_entrada.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {arquivo_entrada}"
        )

    # 2. Ler o JSON bruto
    with arquivo_entrada.open("r", encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    if not isinstance(registros, list):
        raise ValueError("O JSON deve conter uma lista de registros.")

    if not registros:
        raise ValueError("O arquivo JSON não contém registros.")

    print(f"Registros recebidos: {len(registros)}")

    # 3. Transformar o JSON em uma tabela
    df = pd.json_normalize(registros, sep="_")

    # 4. Selecionar e renomear os campos
    colunas = {
        "numeroControlePNCP": "numero_controle_pncp",
        "orgaoEntidade_razaoSocial": "orgao",
        "unidadeOrgao_ufSigla": "uf",
        "unidadeOrgao_municipioNome": "municipio",
        "objetoCompra": "objeto",
        "modalidadeNome": "modalidade",
        "dataPublicacaoPncp": "data_publicacao",
        "dataEncerramentoProposta": "data_encerramento",
        "valorTotalEstimado": "valor_estimado",
        "valorTotalHomologado": "valor_homologado",
        "situacaoCompraNome": "situacao",
        "anoCompra": "ano_compra",
    }

    # Manter somente os campos disponíveis no retorno
    colunas_disponiveis = {
        original: novo
        for original, novo in colunas.items()
        if original in df.columns
    }

    df = df[list(colunas_disponiveis)].rename(
        columns=colunas_disponiveis
    )

    # 5. Limpar espaços extras e quebras de linha dos textos
    colunas_texto = [
        "orgao",
        "uf",
        "municipio",
        "objeto",
        "modalidade",
        "situacao",
    ]

    for coluna in colunas_texto:
        if coluna in df.columns:
            df[coluna] = df[coluna].map(
                lambda valor: (
                    " ".join(valor.split())
                    if isinstance(valor, str)
                    else valor
                )
            )

    # 6. Padronizar as datas
    for coluna in ["data_publicacao", "data_encerramento"]:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(
                df[coluna],
                errors="coerce",
            )

    # 7. Remover registros sem identificador
    if "numero_controle_pncp" in df.columns:
        df["numero_controle_pncp"] = (
            df["numero_controle_pncp"].replace("", pd.NA)
        )

        sem_id = df["numero_controle_pncp"].isna().sum()

        if sem_id:
            print(f"Registros sem identificador removidos: {sem_id}")

        df = df.dropna(subset=["numero_controle_pncp"])

        # Manter a primeira ocorrência de cada contratação
        duplicados = df.duplicated(
            subset=["numero_controle_pncp"]
        ).sum()

        if duplicados:
            print(f"Registros duplicados removidos: {duplicados}")

        df = df.drop_duplicates(
            subset=["numero_controle_pncp"],
            keep="first",
        )

    # 8. Criar a pasta de saída
    arquivo_saida.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 9. Salvar o CSV
    df.to_csv(
        arquivo_saida,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d %H:%M:%S",
    )

    print(f"Registros transformados: {len(df)}")
    print(f"Colunas geradas: {len(df.columns)}")
    print(f"CSV salvo em: {arquivo_saida}")

    print("\nPrévia dos dados:")
    print(df.head(5).to_string(index=False))

    return arquivo_saida


if __name__ == "__main__":
    transformar_dados()