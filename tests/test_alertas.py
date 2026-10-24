from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest
from pydantic import ValidationError

from apoio import escrever_csv, linha
from src import alertas, load




def escrever_yaml(pasta, conteudo):
    arquivo = pasta / "alertas.yml"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_le_destinatarios_com_valores_padrao(tmp_path):
    arquivo = escrever_yaml(tmp_path, """
destinatarios:
  - email: pessoa@exemplo.com
    palavras_chave: ["software", "nuvem"]
    ufs: ["DF", "go"]
    valor_minimo: 50000
    enviar_se_vazio: true
  - email: outra@exemplo.com
""")

    config = alertas.carregar_config(arquivo)

    completo, minimo = config.destinatarios
    assert completo.palavras_chave == ["software", "nuvem"]
    assert completo.ufs == ["DF", "GO"]
    assert completo.valor_minimo == 50000
    assert completo.enviar_se_vazio is True
    # Sem critério nenhum: recebe tudo do dia, e só quando houver algo
    assert minimo.palavras_chave == []
    assert minimo.ufs == []
    assert minimo.valor_minimo is None
    assert minimo.enviar_se_vazio is False


def test_campo_desconhecido_e_erro(tmp_path):
    arquivo = escrever_yaml(tmp_path, """
destinatarios:
  - email: pessoa@exemplo.com
    palavra_chave: ["software"]
""")

    with pytest.raises(ValidationError, match="palavra_chave"):
        alertas.carregar_config(arquivo)


def test_uf_invalida_e_erro(tmp_path):
    arquivo = escrever_yaml(tmp_path, """
destinatarios:
  - email: pessoa@exemplo.com
    ufs: ["DF", "XX"]
""")

    with pytest.raises(ValidationError, match="UF inválida: XX"):
        alertas.carregar_config(arquivo)


def test_email_invalido_e_erro(tmp_path):
    arquivo = escrever_yaml(tmp_path, """
destinatarios:
  - email: pessoa.exemplo.com
""")

    with pytest.raises(ValidationError, match="email"):
        alertas.carregar_config(arquivo)


def test_sem_destinatarios_e_erro(tmp_path):
    arquivo = escrever_yaml(tmp_path, "destinatarios: []\n")

    with pytest.raises(ValidationError, match="destinatarios"):
        alertas.carregar_config(arquivo)

def contratacoes(*linhas):
    # Mesmos tipos que vêm do banco: valor em Decimal, objeto podendo ser None
    return pd.DataFrame(
        linhas,
        columns=["numero_controle_pncp", "objeto", "uf", "valor_estimado"],
    )


def numeros(df):
    return list(df["numero_controle_pncp"])


def test_sem_criterios_recebe_tudo():
    df = contratacoes(
        ("A", "Aquisição de software", "SP", Decimal("100.00")),
        ("B", "Obra de pavimentação", "DF", Decimal("0.00")),
    )

    destinatario = alertas.Destinatario(email="a@exemplo.com")

    assert numeros(alertas.filtrar(df, destinatario)) == ["A", "B"]


def test_qualquer_palavra_chave_sem_acento_nem_maiusculas():
    df = contratacoes(
        ("A", "Licença de SOFTWARE de gestão", "SP", Decimal("100.00")),
        ("B", "Serviços de computação em nuvem", "SP", Decimal("100.00")),
        ("C", "Aquisição de medicamentos", "SP", Decimal("100.00")),
        ("D", None, "SP", Decimal("100.00")),
    )

    destinatario = alertas.Destinatario(
        email="a@exemplo.com", palavras_chave=["Software", "computacao"]
    )

    assert numeros(alertas.filtrar(df, destinatario)) == ["A", "B"]


def test_palavra_chave_acha_inicio_de_palavra_e_nao_o_meio():
    df = contratacoes(
        ("A", "Aquisição de softwares", "SP", Decimal("100.00")),
        ("B", "Equipamentos de TI", "SP", Decimal("100.00")),
        ("C", "Atividades de limpeza", "SP", Decimal("100.00")),
    )

    destinatario = alertas.Destinatario(
        email="a@exemplo.com", palavras_chave=["software", "ti"]
    )

    assert numeros(alertas.filtrar(df, destinatario)) == ["A", "B"]


def test_criterios_valem_juntos():
    df = contratacoes(
        ("A", "Aquisição de software", "DF", Decimal("80000.00")),
        ("B", "Aquisição de software", "SP", Decimal("80000.00")),
        ("C", "Aquisição de software", "GO", Decimal("1000.00")),
        ("D", "Obra de pavimentação", "DF", Decimal("80000.00")),
    )

    destinatario = alertas.Destinatario(
        email="a@exemplo.com",
        palavras_chave=["software"],
        ufs=["DF", "GO"],
        valor_minimo=50000,
    )

    assert numeros(alertas.filtrar(df, destinatario)) == ["A"]

def test_contratacoes_do_dia_inteiro_maiores_primeiro(conexao, tmp_path):
    linhas = [
        linha(numero_controle_pncp="A", data_publicacao="2026-10-21 23:59:59"),
        linha(
            numero_controle_pncp="B",
            data_publicacao="2026-10-22 00:00:00",
            valor_estimado=100,
        ),
        linha(
            numero_controle_pncp="C",
            data_publicacao="2026-10-22 23:59:59",
            valor_estimado=5000,
        ),
        linha(numero_controle_pncp="D", data_publicacao="2026-10-23 00:00:00"),
    ]
    load.carregar_dados(escrever_csv(tmp_path, linhas), conexao)

    resultado = alertas.contratacoes_do_dia(conexao, date(2026, 10, 22))

    assert numeros(resultado) == ["C", "B"]

def para_email(*linhas):
    return pd.DataFrame(linhas)


def contratacao(**campos):
    # Linha no formato que contratacoes_do_dia devolve
    base = {
        "numero_controle_pncp": "A",
        "objeto": "Aquisição de software",
        "orgao": "PREFEITURA DE TESTE",
        "uf": "DF",
        "municipio": "Brasília",
        "valor_estimado": Decimal("1500.50"),
        "data_encerramento": datetime(2026, 10, 30, 9, 0),
        "link_pncp": "https://pncp.gov.br/app/editais/00000000000100/2026/1",
    }
    base.update(campos)
    return base


DIA = date(2026, 10, 22)
DESTINATARIO = alertas.Destinatario(
    email="a@exemplo.com", palavras_chave=["software"], ufs=["DF"]
)


def test_assunto_tem_dia_e_quantidade():
    df = para_email(contratacao(), contratacao(numero_controle_pncp="B"))

    assunto, _ = alertas.montar_email(DESTINATARIO, df, DIA)

    assert assunto == "Alerta PNCP 22/10/2026: 2 contratações"


def test_email_lista_contratacao_formatada_com_link():
    df = para_email(contratacao())

    _, html = alertas.montar_email(DESTINATARIO, df, DIA)

    assert "Aquisição de software" in html
    assert 'href="https://pncp.gov.br/app/editais/00000000000100/2026/1"' in html
    assert "R$ 1.500,50" in html
    assert "30/10/2026 09:00" in html


def test_valor_zero_aparece_como_sigiloso():
    df = para_email(contratacao(valor_estimado=Decimal("0.00")))

    _, html = alertas.montar_email(DESTINATARIO, df, DIA)

    assert "Sigiloso" in html


def test_texto_do_objeto_nao_vira_html():
    df = para_email(contratacao(objeto="Cabo <HDMI> & adaptador"))

    _, html = alertas.montar_email(DESTINATARIO, df, DIA)

    assert "Cabo &lt;HDMI&gt; &amp; adaptador" in html


def test_corpo_mostra_so_as_primeiras_e_avisa_do_csv():
    df = para_email(*[
        contratacao(numero_controle_pncp=str(i)) for i in range(60)
    ])

    _, html = alertas.montar_email(DESTINATARIO, df, DIA)

    assert html.count("https://pncp.gov.br/app/editais/") == alertas.LIMITE_NO_EMAIL
    assert "lista completa está no CSV anexo" in html


def test_dia_sem_resultados():
    df = para_email()

    assunto, html = alertas.montar_email(DESTINATARIO, df, DIA)

    assert assunto == "Alerta PNCP 22/10/2026: nenhuma contratação"
    assert "Nenhuma contratação bateu com seus critérios" in html

class CaixaDeSaida:
    # Faz o papel do servidor de e-mail: guarda o que seria enviado
    def __init__(self):
        self.emails = []

    def enviar(self, to, subject, html_content, files):
        anexos = [pd.read_csv(arquivo, encoding="utf-8-sig") for arquivo in files]
        self.emails.append({"para": to, "assunto": subject, "anexos": anexos})


def config_de(*destinatarios):
    return alertas.ConfigAlertas(destinatarios=list(destinatarios))


def contratacoes_completas(*linhas):
    # Todas as colunas da tabela, como contratacoes_do_dia devolve
    return pd.DataFrame([{**linha(), **contratacao(**campos)} for campos in linhas])


def test_cada_destinatario_recebe_so_o_que_pediu(tmp_path):
    df = contratacoes_completas(
        dict(numero_controle_pncp="A", objeto="Licença de software", uf="DF"),
        dict(numero_controle_pncp="B", objeto="Aquisição de medicamentos", uf="SP"),
        dict(numero_controle_pncp="C", objeto="Medicamentos e software", uf="GO"),
    )
    config = config_de(
        alertas.Destinatario(email="ti@exemplo.com", palavras_chave=["software"]),
        alertas.Destinatario(
            email="saude@exemplo.com", palavras_chave=["medicamento"], ufs=["SP"]
        ),
    )
    caixa = CaixaDeSaida()

    enviados = alertas.enviar_alertas(config, df, DIA, tmp_path, caixa.enviar)

    assert enviados == ["ti@exemplo.com", "saude@exemplo.com"]
    ti, saude = caixa.emails
    assert ti["assunto"] == "Alerta PNCP 22/10/2026: 2 contratações"
    assert list(ti["anexos"][0]["numero_controle_pncp"]) == ["A", "C"]
    assert list(saude["anexos"][0]["numero_controle_pncp"]) == ["B"]


def test_anexo_tem_as_colunas_da_tabela(tmp_path):
    df = contratacoes_completas(dict(numero_controle_pncp="A"))
    config = config_de(alertas.Destinatario(email="a@exemplo.com"))
    caixa = CaixaDeSaida()

    alertas.enviar_alertas(config, df, DIA, tmp_path, caixa.enviar)

    assert list(caixa.emails[0]["anexos"][0].columns) == load.COLUNAS


def test_sem_resultado_so_envia_para_quem_pediu(tmp_path):
    df = contratacoes_completas(dict(objeto="Obra de pavimentação"))
    config = config_de(
        alertas.Destinatario(
            email="quer@exemplo.com", palavras_chave=["software"], enviar_se_vazio=True
        ),
        alertas.Destinatario(email="nao.quer@exemplo.com", palavras_chave=["software"]),
    )
    caixa = CaixaDeSaida()

    enviados = alertas.enviar_alertas(config, df, DIA, tmp_path, caixa.enviar)

    assert enviados == ["quer@exemplo.com"]
    assert caixa.emails[0]["assunto"] == "Alerta PNCP 22/10/2026: nenhuma contratação"
    # Sem CSV vazio anexado
    assert caixa.emails[0]["anexos"] == []

