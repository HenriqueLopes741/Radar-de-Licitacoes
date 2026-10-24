import re
from pathlib import Path

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

# O e-mail mostra as maiores; o resto vai só no CSV anexo
LIMITE_NO_EMAIL = 50


def _reais(valor):
    if valor is None or pd.isna(valor):
        return "—"
    if valor == 0:
        return "Sigiloso"
    # 1,234.56 -> 1.234,56
    return "R$ " + f"{float(valor):,.2f}".translate(str.maketrans(",.", ".,"))


def _data_hora(valor):
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor:%d/%m/%Y %H:%M}"


# autoescape: um objeto com "<" ou "&" aparece como texto, sem quebrar o HTML
_templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)
_templates.filters["reais"] = _reais
_templates.filters["data_hora"] = _data_hora
_templates.filters["data"] = lambda dia: f"{dia:%d/%m/%Y}"


def montar_email(destinatario, df, dia):
    total = len(df)
    if total == 0:
        resumo = "nenhuma contratação"
    elif total == 1:
        resumo = "1 contratação"
    else:
        resumo = f"{total} contratações"
    assunto = f"Alerta PNCP {dia:%d/%m/%Y}: {resumo}"

    html = _templates.get_template("alerta.html").render(
        destinatario=destinatario,
        dia=dia,
        total=total,
        contratacoes=df.head(LIMITE_NO_EMAIL).to_dict("records"),
    )
    return assunto, html

def enviar_alertas(config, df, dia, pasta, enviar):
    # "enviar" recebe to, subject, html_content e files, como o
    # send_email_smtp do Airflow; nos testes, uma função que só anota
    enviados = []
    for destinatario in config.destinatarios:
        filtradas = filtrar(df, destinatario)
        if filtradas.empty and not destinatario.enviar_se_vazio:
            continue

        assunto, html = montar_email(destinatario, filtradas, dia)

        anexos = []
        if not filtradas.empty:
            # Mesmo nome para todos: cada CSV é enviado antes do próximo sobrescrevê-lo
            csv = Path(pasta) / f"contratacoes-pncp-{dia:%Y-%m-%d}.csv"
            filtradas[COLUNAS].to_csv(csv, index=False, encoding="utf-8-sig")
            anexos.append(str(csv))

        enviar(to=destinatario.email, subject=assunto, html_content=html, files=anexos)
        enviados.append(destinatario.email)

    return enviados
