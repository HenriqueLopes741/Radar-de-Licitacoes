import json

import pandas as pd
import pytest

from src import transform


COLUNAS_ESPERADAS = [
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
]


def registro(**campos):
    # Registro no formato retornado pela API do PNCP
    base = {
        "numeroControlePNCP": "00000000000100-1-000001/2026",
        "orgaoEntidade": {"razaoSocial": "PREFEITURA DE TESTE"},
        "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
        "objetoCompra": "Aquisição de medicamentos",
        "modalidadeNome": "Pregão - Eletrônico",
        "dataPublicacaoPncp": "2026-10-01T08:30:00",
        "dataEncerramentoProposta": "2026-10-15T09:00:00",
        "valorTotalEstimado": 1500.5,
        "valorTotalHomologado": None,
        "situacaoCompraNome": "Divulgada no PNCP",
        "anoCompra": 2026,
    }
    base.update(campos)
    return base


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    entrada = tmp_path / "raw/contratacoes.json"
    saida = tmp_path / "processed/contratacoes.csv"
    monkeypatch.setattr(transform, "ARQUIVO_ENTRADA", entrada)
    monkeypatch.setattr(transform, "ARQUIVO_SAIDA", saida)
    return entrada, saida


def executar(arquivos, registros):
    entrada, saida = arquivos
    entrada.parent.mkdir(parents=True, exist_ok=True)
    entrada.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")

    transform.transformar_dados()

    return pd.read_csv(saida, encoding="utf-8-sig")


def test_gera_csv_com_colunas_renomeadas(arquivos):
    df = executar(arquivos, [registro()])

    assert list(df.columns) == COLUNAS_ESPERADAS
    linha = df.iloc[0]
    assert linha["orgao"] == "PREFEITURA DE TESTE"
    assert linha["uf"] == "SP"
    assert linha["municipio"] == "São Paulo"
    assert linha["valor_estimado"] == 1500.5
    assert linha["ano_compra"] == 2026


def test_ignora_campos_ausentes_no_retorno(arquivos):
    r = registro()
    del r["valorTotalHomologado"]

    df = executar(arquivos, [r])

    assert "valor_homologado" not in df.columns
    assert len(df) == 1


def test_remove_duplicatas_mantendo_a_primeira(arquivos):
    df = executar(arquivos, [
        registro(numeroControlePNCP="A", objetoCompra="primeiro"),
        registro(numeroControlePNCP="A", objetoCompra="segundo"),
        registro(numeroControlePNCP="B"),
    ])

    assert len(df) == 2
    assert df.loc[df["numero_controle_pncp"] == "A", "objeto"].item() == "primeiro"


def test_remove_registros_sem_identificador(arquivos):
    df = executar(arquivos, [
        registro(numeroControlePNCP="A"),
        registro(numeroControlePNCP=""),
        registro(numeroControlePNCP=None),
    ])

    assert df["numero_controle_pncp"].tolist() == ["A"]


def test_limpa_espacos_e_quebras_de_linha(arquivos):
    df = executar(arquivos, [
        registro(objetoCompra="  Aquisição de\r\nmedicamentos\t e   insumos  "),
    ])

    assert df.loc[0, "objeto"] == "Aquisição de medicamentos e insumos"


def test_padroniza_datas_e_anula_datas_invalidas(arquivos):
    df = executar(arquivos, [
        registro(numeroControlePNCP="A"),
        registro(numeroControlePNCP="B", dataEncerramentoProposta="data-invalida"),
    ])

    assert df.loc[0, "data_publicacao"] == "2026-10-01 08:30:00"
    assert df.loc[0, "data_encerramento"] == "2026-10-15 09:00:00"
    assert pd.isna(df.loc[1, "data_encerramento"])


def test_aceita_caminhos_de_entrada_e_saida(tmp_path):
    entrada = tmp_path / "raw/contratacoes_20261013.json"
    saida = tmp_path / "processed/contratacoes_20261013.csv"
    entrada.parent.mkdir(parents=True)
    entrada.write_text(json.dumps([registro()], ensure_ascii=False), encoding="utf-8")

    retorno = transform.transformar_dados(arquivo_entrada=entrada, arquivo_saida=saida)

    assert retorno == saida
    assert len(pd.read_csv(saida, encoding="utf-8-sig")) == 1


def test_erro_quando_arquivo_nao_existe(arquivos):
    with pytest.raises(FileNotFoundError):
        transform.transformar_dados()


@pytest.mark.parametrize("conteudo", [[], {"data": []}])
def test_erro_quando_json_vazio_ou_nao_e_lista(arquivos, conteudo):
    with pytest.raises(ValueError):
        executar(arquivos, conteudo)
