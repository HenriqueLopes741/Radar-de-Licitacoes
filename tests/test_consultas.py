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
