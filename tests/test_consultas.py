from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from apoio import escrever_csv, linha
from dashboard import consultas
from src import load



def carregar(conexao, pasta, linhas):
    # Grava pelo próprio carregador, para a tabela ficar igual à de produção
    load.carregar_dados(escrever_csv(pasta, linhas), conexao)


def test_sem_filtro_devolve_todas(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A"),
        linha(numero_controle_pncp="B"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao)

    assert sorted(resultado["numero_controle_pncp"]) == ["A", "B"]


def test_filtra_por_uf(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", uf="SP"),
        linha(numero_controle_pncp="B", uf="DF"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao, uf="DF")

    assert list(resultado["numero_controle_pncp"]) == ["B"]


def test_mais_recentes_primeiro(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", data_publicacao="2026-10-01 08:00:00"),
        linha(numero_controle_pncp="B", data_publicacao="2026-10-02 08:00:00"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao)

    assert list(resultado["numero_controle_pncp"]) == ["B", "A"]


def test_filtra_por_palavra_no_objeto_sem_diferenciar_maiusculas(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", objeto="Aquisição de MEDICAMENTOS"),
        linha(numero_controle_pncp="B", objeto="Obra de pavimentação"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao, palavra_chave="medicamento")

    assert list(resultado["numero_controle_pncp"]) == ["A"]


def test_filtra_por_parte_do_nome_do_orgao(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", orgao="PREFEITURA MUNICIPAL DE CAMPINAS"),
        linha(numero_controle_pncp="B", orgao="MINISTERIO DA SAUDE"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao, orgao="campinas")

    assert list(resultado["numero_controle_pncp"]) == ["A"]


def test_filtra_por_municipio_exato(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", municipio="São Paulo", uf="SP"),
        linha(numero_controle_pncp="B", municipio="São Paulo de Olivença", uf="AM"),
    ])

    resultado = consultas.filtrar_contratacoes(conexao, municipio="São Paulo")

    assert list(resultado["numero_controle_pncp"]) == ["A"]


def test_filtra_por_faixa_de_valor_estimado(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", valor_estimado=100),
        linha(numero_controle_pncp="B", valor_estimado=1000),
        linha(numero_controle_pncp="C", valor_estimado=10000),
    ])

    resultado = consultas.filtrar_contratacoes(conexao, valor_min=500, valor_max=5000)

    assert list(resultado["numero_controle_pncp"]) == ["B"]


def test_filtra_por_prazo_incluindo_o_dia_final_inteiro(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", data_encerramento="2026-10-10 10:00:00"),
        linha(numero_controle_pncp="B", data_encerramento="2026-10-15 09:00:00"),
        linha(numero_controle_pncp="C", data_encerramento="2026-10-20 10:00:00"),
    ])

    resultado = consultas.filtrar_contratacoes(
        conexao, encerra_de=date(2026, 10, 12), encerra_ate=date(2026, 10, 15)
    )

    assert list(resultado["numero_controle_pncp"]) == ["B"]


def contratacoes(*linhas):
    # Mesmos tipos que o filtro devolve: datetime e Decimal (NUMERIC no banco)
    return pd.DataFrame(
        linhas,
        columns=["numero_controle_pncp", "uf", "data_publicacao", "valor_estimado"],
    )


def test_resumo_por_dia_junta_horarios_do_mesmo_dia(tmp_path):
    df = contratacoes(
        ("A", "SP", datetime(2026, 10, 1, 8, 0), Decimal("100.50")),
        ("B", "SP", datetime(2026, 10, 1, 17, 0), None),
        ("C", "DF", datetime(2026, 10, 2, 9, 0), Decimal("200.00")),
    )

    resultado = consultas.resumo_por_dia(df)

    assert resultado.to_dict("records") == [
        {"dia": date(2026, 10, 1), "quantidade": 2, "valor_total": 100.5},
        {"dia": date(2026, 10, 2), "quantidade": 1, "valor_total": 200.0},
    ]


def test_resumo_por_uf(tmp_path):
    df = contratacoes(
        ("A", "SP", datetime(2026, 10, 1, 8, 0), Decimal("100.50")),
        ("B", "SP", datetime(2026, 10, 1, 17, 0), Decimal("50.00")),
        ("C", "DF", datetime(2026, 10, 2, 9, 0), Decimal("200.00")),
    )

    resultado = consultas.resumo_por_uf(df)

    assert resultado.to_dict("records") == [
        {"uf": "DF", "quantidade": 1, "valor_total": 200.0},
        {"uf": "SP", "quantidade": 2, "valor_total": 150.5},
    ]


def test_resumo_de_resultado_vazio_nao_quebra():
    # Filtro sem resultado: o DataFrame vem sem linhas e sem tipo de data
    vazio = contratacoes()

    assert consultas.resumo_por_dia(vazio).empty
    assert consultas.resumo_por_uf(vazio).empty

def test_lista_ufs_sem_repetir_e_em_ordem(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", uf="SP"),
        linha(numero_controle_pncp="B", uf="DF"),
        linha(numero_controle_pncp="C", uf="SP"),
    ])

    assert consultas.listar_ufs(conexao) == ["DF", "SP"]


def test_lista_municipios_so_da_uf_pedida(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", uf="SP", municipio="Santos"),
        linha(numero_controle_pncp="B", uf="SP", municipio="Campinas"),
        linha(numero_controle_pncp="C", uf="AM", municipio="Manaus"),
    ])

    assert consultas.listar_municipios(conexao, "SP") == ["Campinas", "Santos"]

def test_indicadores_ignoram_valor_zero_na_mediana():
    df = pd.DataFrame({
        "data_encerramento": [
            datetime(2026, 10, 22, 9, 0),
            datetime(2026, 10, 23, 9, 0),
            datetime(2026, 10, 30, 9, 0),
            None,
        ],
        "valor_estimado": [
            Decimal("0.00"), Decimal("100.00"), Decimal("300.00"), Decimal("0.00"),
        ],
    })

    resultado = consultas.indicadores(df, hoje=date(2026, 10, 23))

    assert resultado == {
        "contratacoes": 4,
        # A que encerra hoje às 9h ainda conta como aberta
        "abertas": 2,
        "mediana_valor": 200.0,
        "fatia_sem_valor": 0.5,
    }


def test_dias_para_encerrar_contam_a_partir_de_hoje():
    df = pd.DataFrame({
        "data_encerramento": [
            datetime(2026, 10, 22, 9, 0),
            datetime(2026, 10, 23, 18, 0),
            datetime(2026, 10, 30, 9, 0),
        ],
    })

    resultado = consultas.com_dias_para_encerrar(df, hoje=date(2026, 10, 23))

    assert list(resultado["encerra_em"]) == [-1, 0, 7]


def test_periodo_publicado(conexao, tmp_path):
    carregar(conexao, tmp_path, [
        linha(numero_controle_pncp="A", data_publicacao="2026-10-01 08:00:00"),
        linha(numero_controle_pncp="B", data_publicacao="2026-10-22 17:00:00"),
    ])

    assert consultas.periodo_publicado(conexao) == (date(2026, 10, 1), date(2026, 10, 22))

def test_sem_tabela_nao_tem_dados(conexao):
    # A fixture apaga a tabela e nada foi carregado
    assert consultas.tem_dados(conexao) is False


def test_com_tabela_tem_dados(conexao, tmp_path):
    carregar(conexao, tmp_path, [linha()])

    assert consultas.tem_dados(conexao) is True
