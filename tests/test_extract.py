import json
from unittest.mock import Mock

import pytest
import requests

from src import extract


def resposta(status=200, dados=None, headers=None):
    r = Mock()
    r.status_code = status
    r.ok = status < 400
    r.headers = headers or {}
    r.text = ""
    r.json.return_value = dados
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(str(status))
    return r


def pagina(registros, total_paginas):
    return {
        "data": registros,
        "totalPaginas": total_paginas,
        "totalRegistros": 0,
    }


@pytest.fixture
def esperas(monkeypatch):
    # Registra as pausas em vez de esperar de verdade
    chamadas = []
    monkeypatch.setattr(extract.time, "sleep", chamadas.append)
    return chamadas


@pytest.fixture
def get(tmp_path, monkeypatch, esperas):
    # Salva o JSON numa pasta temporária e substitui a API por um mock
    monkeypatch.chdir(tmp_path)
    mock_get = Mock()
    monkeypatch.setattr(requests.Session, "get", mock_get)
    return mock_get


def ler_json_salvo(arquivo):
    return json.loads(arquivo.read_text(encoding="utf-8"))


def test_junta_todas_as_paginas_e_salva_json(get):
    get.side_effect = [
        resposta(dados=pagina([{"numeroControlePNCP": "1"}, {"numeroControlePNCP": "2"}], 2)),
        resposta(dados=pagina([{"numeroControlePNCP": "3"}], 2)),
    ]

    arquivo = extract.extrair_dados()

    salvo = ler_json_salvo(arquivo)
    assert [r["numeroControlePNCP"] for r in salvo] == ["1", "2", "3"]
    assert get.call_count == 2


def test_envia_numero_da_pagina_e_filtros(get):
    get.side_effect = [
        resposta(dados=pagina([{"numeroControlePNCP": "1"}], 2)),
        resposta(dados=pagina([{"numeroControlePNCP": "2"}], 2)),
    ]

    extract.extrair_dados()

    paginas = [c.kwargs["params"]["pagina"] for c in get.call_args_list]
    assert paginas == [1, 2]

    params = get.call_args_list[0].kwargs["params"]
    assert params["tamanhoPagina"] <= 50  # a API recusa páginas maiores
    assert params["dataInicial"] == extract.PARAMS["dataInicial"]


def test_tenta_de_novo_apos_429(get, esperas):
    get.side_effect = [
        resposta(429),
        resposta(dados=pagina([{"numeroControlePNCP": "1"}], 1)),
    ]

    arquivo = extract.extrair_dados()

    assert get.call_count == 2
    assert extract.ESPERA_APOS_429 in esperas
    assert len(ler_json_salvo(arquivo)) == 1


def test_respeita_retry_after_da_api(get, esperas):
    get.side_effect = [
        resposta(429, headers={"Retry-After": "12"}),
        resposta(dados=pagina([{"numeroControlePNCP": "1"}], 1)),
    ]

    extract.extrair_dados()

    assert esperas[0] == 12


def test_desiste_apos_max_tentativas(get):
    get.side_effect = [resposta(429)] * extract.MAX_TENTATIVAS

    with pytest.raises(requests.HTTPError):
        extract.extrair_dados()

    assert get.call_count == extract.MAX_TENTATIVAS


def test_erro_400_nao_tenta_de_novo(get):
    get.side_effect = [resposta(400)]

    with pytest.raises(requests.HTTPError):
        extract.extrair_dados()

    assert get.call_count == 1


def test_para_quando_pagina_vem_vazia(get):
    get.side_effect = [resposta(dados=pagina([], 5))]

    arquivo = extract.extrair_dados()

    assert get.call_count == 1
    assert ler_json_salvo(arquivo) == []


def test_para_quando_api_responde_204(get):
    get.side_effect = [resposta(204)]

    arquivo = extract.extrair_dados()

    assert get.call_count == 1
    assert ler_json_salvo(arquivo) == []


def test_envia_datas_informadas_e_salva_um_arquivo_por_dia(get, tmp_path):
    get.side_effect = [resposta(dados=pagina([{"numeroControlePNCP": "1"}], 1))]

    arquivo = extract.extrair_dados(data_inicial="20261013", data_final="20261013")

    params = get.call_args.kwargs["params"]
    assert params["dataInicial"] == "20261013"
    assert params["dataFinal"] == "20261013"
    assert arquivo == extract.PASTA_SAIDA / "contratacoes_20261013_m6.json"
    assert (tmp_path / arquivo).exists()


def test_nome_do_arquivo_inclui_periodo_e_modalidade():
    assert extract.caminho_arquivo_bruto("20261001", "20261002", 6).name == (
        "contratacoes_20261001_20261002_m6.json"
    )


def test_envia_modalidade_informada(get):
    get.side_effect = [resposta(dados=pagina([{"numeroControlePNCP": "1"}], 1))]

    arquivo = extract.extrair_dados(
        data_inicial="20261013", data_final="20261013", modalidade=8
    )

    assert get.call_args.kwargs["params"]["codigoModalidadeContratacao"] == 8
    assert arquivo.name == "contratacoes_20261013_m8.json"
