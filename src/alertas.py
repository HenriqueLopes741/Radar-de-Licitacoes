import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.load import COLUNAS


UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


class Destinatario(BaseModel):
    # Campo desconhecido é erro: um "palavra_chave" digitado errado
    # seria ignorado em silêncio e a pessoa receberia tudo
    model_config = ConfigDict(extra="forbid")

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    palavras_chave: list[str] = []
    ufs: list[str] = []
    valor_minimo: float | None = Field(default=None, ge=0)
    enviar_se_vazio: bool = False

    @field_validator("ufs")
    @classmethod
    def ufs_validas(cls, ufs):
        ufs = [uf.upper() for uf in ufs]
        invalidas = sorted(set(ufs) - UFS)
        if invalidas:
            raise ValueError(f"UF inválida: {', '.join(invalidas)}")
        return ufs


class ConfigAlertas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destinatarios: list[Destinatario] = Field(min_length=1)


def carregar_config(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return ConfigAlertas.model_validate(yaml.safe_load(arquivo))

def _sem_acento(textos):
    # "Aquisição" -> "aquisicao": o NFKD separa a letra do acento, e o
    # encode para ASCII descarta o acento
    return (
        textos.fillna("")
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.lower()
    )


def filtrar(df, destinatario):
    # Critério vazio não filtra; os critérios preenchidos valem juntos
    filtro = pd.Series(True, index=df.index)

    if destinatario.palavras_chave:
        palavras = _sem_acento(pd.Series(destinatario.palavras_chave))
        # \b no começo: "software" acha "softwares", mas "ti" não acha "atividade"
        padrao = "|".join(rf"\b{re.escape(palavra)}" for palavra in palavras)
        filtro &= _sem_acento(df["objeto"]).str.contains(padrao)

    if destinatario.ufs:
        filtro &= df["uf"].isin(destinatario.ufs)

    if destinatario.valor_minimo is not None:
        filtro &= df["valor_estimado"].astype(float) >= destinatario.valor_minimo

    return df[filtro]

# Intervalo em vez de "data_publicacao::date = %s": comparando a coluna
# sem transformá-la, o Postgres consegue usar o índice de data_publicacao
CONTRATACOES_DO_DIA = """
SELECT * FROM contratacoes
WHERE data_publicacao >= %(dia)s
  AND data_publicacao < %(dia)s + INTERVAL '1 day'
ORDER BY valor_estimado DESC NULLS LAST
"""


def contratacoes_do_dia(conexao, dia):
    with conexao.cursor() as cursor:
        cursor.execute(CONTRATACOES_DO_DIA, {"dia": dia})
        colunas = [coluna.name for coluna in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=colunas)

# O e-mail mostra as maiores; o resto vai só no CSV anexo. Com 50, o HTML
# chegava perto dos 102 KB a partir dos quais o Gmail corta a mensagem
LIMITE_NO_EMAIL = 30

# Objetos passam de 1.000 caracteres; o texto inteiro está no edital e no CSV
LIMITE_DO_OBJETO = 160

FUSO = ZoneInfo("America/Sao_Paulo")


def _reais(valor):
    if valor is None or pd.isna(valor):
        return "—"
    if valor == 0:
        return "Sigiloso"
    # 1,234.56 -> 1.234,56
    return "R$ " + f"{float(valor):,.2f}".translate(str.maketrans(",.", ".,"))


def _reais_curto(valor):
    # R$ 3,6 mi, R$ 850 mil: cabe no assunto e no resumo
    if valor is None or pd.isna(valor) or valor == 0:
        return "—"
    valor = float(valor)
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi")):
        if valor >= limite:
            return "R$ " + f"{valor / limite:.1f}".replace(".", ",") + f" {sufixo}"
    if valor >= 1e3:
        return f"R$ {valor / 1e3:.0f} mil"
    return _reais(valor)


def _resumir(texto, limite=LIMITE_DO_OBJETO):
    texto = texto or ""
    if len(texto) <= limite:
        return texto
    # Corta na última palavra inteira, sem deixar pontuação antes das reticências
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",;.:-") + "…"


def _dias_ate(encerramento, hoje):
    if encerramento is None or pd.isna(encerramento):
        return None
    return (pd.Timestamp(encerramento).date() - hoje).days


# autoescape: um objeto com "<" ou "&" aparece como texto, sem quebrar o HTML.
# trim_blocks e lstrip_blocks tiram as linhas em branco das tags do Jinja,
# que somam alguns KB num e-mail com dezenas de contratações
_templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_templates.filters["reais"] = _reais
_templates.filters["reais_curto"] = _reais_curto
_templates.filters["resumir"] = _resumir
_templates.filters["dias_ate"] = _dias_ate
_templates.filters["data"] = lambda dia: f"{dia:%d/%m/%Y}"
_templates.filters["dia_mes"] = lambda dia: f"{dia:%d/%m}"


def _criterio(destinatario):
    # O critério principal no assunto distingue um alerta do outro na caixa de entrada
    if destinatario.palavras_chave:
        palavras = destinatario.palavras_chave
        return " de " + ", ".join(palavras[:2]) + ("…" if len(palavras) > 2 else "")
    if destinatario.ufs:
        ufs = destinatario.ufs
        return " em " + ", ".join(ufs[:3]) + ("…" if len(ufs) > 3 else "")
    return ""


def _resumo(df, hoje):
    valores = df["valor_estimado"].astype(float)
    # Valor zero é orçamento sigiloso: não conta como "maior valor"
    divulgados = valores[valores > 0]
    maior = divulgados.idxmax() if not divulgados.empty else None

    # Comparando com Timestamp, prazos vazios (NaT) só ficam de fora; com uma
    # date, o pandas não compara uma coluna em que todos os prazos são vazios
    encerramentos = pd.to_datetime(df["data_encerramento"])
    abertas = encerramentos[encerramentos.dt.normalize() >= pd.Timestamp(hoje)]
    proximo_prazo = abertas.min() if not abertas.empty else None

    return {
        "maior_valor": valores[maior] if maior is not None else None,
        "maior_objeto": df.loc[maior, "objeto"] if maior is not None else None,
        "proximo_prazo": proximo_prazo,
        "dias_proximo": _dias_ate(proximo_prazo, hoje),
    }


def montar_email(destinatario, df, dia, hoje=None):
    # "hoje" conta os dias até o encerramento; o alerta sai à meia-noite
    # seguinte ao dia publicado, então em geral é o dia seguinte a "dia"
    hoje = hoje or datetime.now(FUSO).date()
    total = len(df)
    criterio = _criterio(destinatario)

    if total == 0:
        resumo = None
        assunto = f"PNCP: nenhuma contratação{criterio} · {dia:%d/%m}"
        previa = "Nenhuma contratação bateu com os seus critérios neste dia."
    else:
        resumo = _resumo(df, hoje)
        quantidade = "1 contratação" if total == 1 else f"{total} contratações"
        maior = (
            f" · maior {_reais_curto(resumo['maior_valor'])}"
            if resumo["maior_valor"] is not None
            else ""
        )
        assunto = f"PNCP: {quantidade}{criterio}{maior} · {dia:%d/%m}"

        partes = []
        if resumo["proximo_prazo"] is not None:
            partes.append(f"Próximo prazo: {resumo['proximo_prazo']:%d/%m}.")
        if resumo["maior_objeto"]:
            partes.append(f"Maior: {_resumir(resumo['maior_objeto'], 70)}")
        previa = " ".join(partes)

    html = _templates.get_template("alerta.html").render(
        destinatario=destinatario,
        dia=dia,
        hoje=hoje,
        total=total,
        resumo=resumo,
        previa=previa,
        contratacoes=df.head(LIMITE_NO_EMAIL).to_dict("records"),
    )
    return assunto, html

def enviar_alertas(config, df, dia, pasta, enviar, hoje=None):
    # "enviar" recebe to, subject, html_content e files, como o
    # send_email_smtp do Airflow; nos testes, uma função que só anota
    enviados = []
    for destinatario in config.destinatarios:
        filtradas = filtrar(df, destinatario)
        if filtradas.empty and not destinatario.enviar_se_vazio:
            continue

        assunto, html = montar_email(destinatario, filtradas, dia, hoje)

        anexos = []
        if not filtradas.empty:
            # Mesmo nome para todos: cada CSV é enviado antes do próximo sobrescrevê-lo
            csv = Path(pasta) / f"contratacoes-pncp-{dia:%Y-%m-%d}.csv"
            filtradas[COLUNAS].to_csv(csv, index=False, encoding="utf-8-sig")
            anexos.append(str(csv))

        enviar(to=destinatario.email, subject=assunto, html_content=html, files=anexos)
        enviados.append(destinatario.email)

    return enviados
