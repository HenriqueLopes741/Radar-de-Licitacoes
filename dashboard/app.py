from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from dashboard import consultas

st.set_page_config(page_title="Contratações PNCP", layout="wide")

# Fuso dos prazos do PNCP; o container roda em UTC, que já "vira o dia" às 21h
hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()


# Cada consulta abre e fecha a própria conexão; o cache evita repetir
# a ida ao banco quando a pessoa só mexe na tela sem mudar os filtros
@st.cache_data(ttl="10m")
def ufs():
    with closing(consultas.conectar()) as conexao:
        return consultas.listar_ufs(conexao)


@st.cache_data(ttl="10m")
def municipios(uf):
    with closing(consultas.conectar()) as conexao:
        return consultas.listar_municipios(conexao, uf)


@st.cache_data(ttl="10m")
def contratacoes(**filtros):
    with closing(consultas.conectar()) as conexao:
        return consultas.filtrar_contratacoes(conexao, **filtros)


@st.cache_data(ttl="10m")
def periodo():
    with closing(consultas.conectar()) as conexao:
        return consultas.periodo_publicado(conexao)


def em_reais(valor):
    # 1,234.56 -> 1.234,56
    return "R$ " + f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))


with st.sidebar:
    st.header("Filtros")
    so_abertas = st.toggle("Só as que ainda estão abertas")
    uf = st.selectbox("UF", ufs(), index=None, placeholder="Todas")
    municipio = st.selectbox(
        "Município",
        municipios(uf) if uf else [],
        index=None,
        placeholder="Todos" if uf else "Escolha uma UF antes",
        disabled=not uf,
    )
    orgao = st.text_input("Órgão (parte do nome)")
    palavra_chave = st.text_input("Palavra-chave no objeto")
    valor_min = st.number_input("Valor estimado mínimo (R$)", min_value=0.0, value=None)
    valor_max = st.number_input("Valor estimado máximo (R$)", min_value=0.0, value=None)
    # Intervalo: devolve 0, 1 ou 2 datas, conforme o que já foi escolhido
    prazo = st.date_input("Encerramento entre", value=(), format="DD/MM/YYYY")

encerra_de = prazo[0] if len(prazo) > 0 else None
if so_abertas:
    # Uma data inicial escolhida depois de hoje continua valendo
    encerra_de = max(encerra_de, hoje) if encerra_de else hoje

df = contratacoes(
    uf=uf,
    municipio=municipio,
    orgao=orgao,
    palavra_chave=palavra_chave,
    valor_min=valor_min,
    valor_max=valor_max,
    encerra_de=encerra_de,
    encerra_ate=prazo[1] if len(prazo) > 1 else None,
)

st.title("Pregões eletrônicos publicados no PNCP")
inicio, fim = periodo()
st.caption(f"Dados de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")

if df.empty:
    st.info("Nenhuma contratação encontrada com esses filtros.")
    st.stop()

numeros = consultas.indicadores(df, hoje)
total, abertas, mediana, sem_valor = st.columns(4)
total.metric("Contratações", f"{numeros['contratacoes']:,}".replace(",", "."))
abertas.metric("Ainda abertas", f"{numeros['abertas']:,}".replace(",", "."))
mediana.metric(
    "Valor estimado típico",
    em_reais(numeros["mediana_valor"]) if numeros["mediana_valor"] else "—",
    help="Mediana, sem contar as de valor sigiloso. A soma engana: "
    "poucas contratações gigantes dominam o total.",
)
sem_valor.metric(
    "Sem valor divulgado",
    f"{numeros['fatia_sem_valor']:.0%}",
    help="Valor estimado zerado, em geral por orçamento sigiloso.",
)

por_dia = consultas.resumo_por_dia(df)
st.subheader("Por dia de publicação")
quantidade, soma = st.columns(2)
quantidade.bar_chart(por_dia, x="dia", y="quantidade", x_label="", y_label="Contratações")
soma.bar_chart(por_dia, x="dia", y="valor_total", x_label="", y_label="Valor estimado (R$)")

por_uf = consultas.resumo_por_uf(df)
st.subheader("Por UF")
quantidade, soma = st.columns(2)
quantidade.bar_chart(por_uf, x="uf", y="quantidade", x_label="", y_label="Contratações")
soma.bar_chart(por_uf, x="uf", y="valor_total", x_label="", y_label="Valor estimado (R$)")

st.subheader("Contratações")
tabela = consultas.com_dias_para_encerrar(df, hoje)
if so_abertas:
    # Quem procura o que disputar quer ver primeiro o que encerra antes
    tabela = tabela.sort_values("data_encerramento")
st.dataframe(
    tabela,
    hide_index=True,
    column_order=[
        "data_encerramento",
        "encerra_em",
        "uf",
        "municipio",
        "orgao",
        "objeto",
        "valor_estimado",
        "link_pncp",
    ],
    column_config={
        "data_encerramento": st.column_config.DatetimeColumn(
            "Encerramento", format="DD/MM/YYYY HH:mm"
        ),
        "encerra_em": st.column_config.NumberColumn("Encerra em", format="%d dias"),
        "uf": "UF",
        "municipio": "Município",
        "orgao": "Órgão",
        "objeto": st.column_config.TextColumn("Objeto", width="large"),
        "valor_estimado": st.column_config.NumberColumn(
            "Valor estimado (R$)", format="localized"
        ),
        "link_pncp": st.column_config.LinkColumn("PNCP", display_text="Abrir"),
    },
)
st.download_button(
    "Baixar CSV",
    df.to_csv(index=False).encode("utf-8-sig"),
    file_name="contratacoes.csv",
    mime="text/csv",
)
