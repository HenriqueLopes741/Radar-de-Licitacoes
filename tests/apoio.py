import pandas as pd


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
