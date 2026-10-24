from apoio import escrever_csv, linha
from src import load

# A fixture conexao (banco de testes) fica no conftest.py


def consultar(conexao, sql):
    with conexao.cursor() as cursor: 
        cursor.execute(sql)
        return cursor.fetchall()

def test_carrega_as_contratacoes_do_csv(conexao, tmp_path): 
    csv = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A"),
        linha(numero_controle_pncp="B"),
    ])

    load.carregar_dados(csv, conexao)

    assert consultar(
        conexao, 
        "SELECT numero_controle_pncp FROM contratacoes ORDER BY 1",
    ) == [("A",), ("B",)]

def test_carregar_o_mesmo_csv_duas_vezes_nao_duplica(conexao, tmp_path):
    csv = escrever_csv(tmp_path, [linha(numero_controle_pncp="A")])

    load.carregar_dados(csv, conexao)
    load.carregar_dados(csv, conexao)

    assert consultar(conexao, "SELECT count(*) FROM contratacoes") == [(1,)]

def test_atualiza_a_contratacao_que_mudou(conexao, tmp_path):
    antes = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A", situacao="Divulgada no PNCP"),
    ])
    load.carregar_dados(antes, conexao)

    depois = escrever_csv(tmp_path, [
        linha(numero_controle_pncp="A", situacao="Homologada"),
    ])
    load.carregar_dados(depois, conexao)

    assert consultar(conexao, "SELECT situacao FROM contratacoes") == [
        ("Homologada",),
    ]

def test_campos_vazios_viram_nulos(conexao, tmp_path):
    csv = escrever_csv(tmp_path, [
        linha(valor_homologado=None, data_encerramento=None),
    ])

    load.carregar_dados(csv, conexao)

    assert consultar(
        conexao,
        "SELECT valor_homologado IS NULL, data_encerramento IS NULL"
        " FROM contratacoes",
    ) == [(True, True)]
