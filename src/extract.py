import json
import time
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

PARAMS = {
    "dataInicial": "20261001",
    "dataFinal": "20261002",
    "codigoModalidadeContratacao": 6,
    "pagina": 1,
    "tamanhoPagina": 50,
}

MAX_TENTATIVAS = 5
# A API do PNCP aceita ~8 requisições por janela de ~45s
PAUSA_ENTRE_PAGINAS = 6
ESPERA_APOS_429 = 30

PASTA_SAIDA = Path("data/raw")

FUSO = ZoneInfo("America/Sao_Paulo")


def dia_a_processar(data, inicio_intervalo):
    # Data informada ao acionar a DAG; senão, o dia que o intervalo da execução cobre
    if data:
        return date.fromisoformat(data).strftime("%Y%m%d")

    return inicio_intervalo.astimezone(FUSO).strftime("%Y%m%d")


def caminho_arquivo_bruto(data_inicial, data_final, modalidade):
    # Um arquivo por período e modalidade, para não sobrescrever as execuções anteriores
    
    if data_inicial == data_final:
        periodo = data_inicial
    else:
        periodo = f"{data_inicial}_{data_final}"

    return PASTA_SAIDA / f"contratacoes_{periodo}_m{modalidade}.json"


def extrair_dados(
    data_inicial=PARAMS["dataInicial"],
    data_final=PARAMS["dataFinal"],
    modalidade=PARAMS["codigoModalidadeContratacao"],
):
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    todos_registros = []
    pagina = 1
    total_paginas = None

    with requests.Session() as session:
        while total_paginas is None or pagina <= total_paginas:
            params = PARAMS.copy()
            params["dataInicial"] = data_inicial
            params["dataFinal"] = data_final
            params["codigoModalidadeContratacao"] = modalidade
            params["pagina"] = pagina

            for tentativa in range(1, MAX_TENTATIVAS + 1):
                response = session.get(
                    URL,
                    params=params,
                    timeout=60,
                )

                print(f"Página {pagina} - HTTP {response.status_code}")

                if response.status_code != 429:
                    break

                espera = int(response.headers.get("Retry-After", ESPERA_APOS_429))
                print(
                    f"Limite de requisições atingido. "
                    f"Aguardando {espera}s (tentativa {tentativa}/{MAX_TENTATIVAS})"
                )
                time.sleep(espera)

            if not response.ok:
                print(response.text)
            response.raise_for_status()

            # A API responde 204 (sem corpo) quando não há contratações
            if response.status_code == 204:
                print("Nenhuma contratação encontrada no período.")
                break

            dados = response.json()
            registros = dados.get("data", [])

            if total_paginas is None:
                total_paginas = dados["totalPaginas"]
                print(f"Total de páginas: {total_paginas}")
                print(f"Total informado pela API: {dados['totalRegistros']}")

            if not registros:
                print("Página sem registros. Encerrando a extração.")
                break

            todos_registros.extend(registros)

            print(
                f"Registros recebidos: {len(registros)} | "
                f"Acumulado: {len(todos_registros)}"
            )

            pagina += 1
            time.sleep(PAUSA_ENTRE_PAGINAS)

    arquivo = caminho_arquivo_bruto(data_inicial, data_final, modalidade)

    with arquivo.open("w", encoding="utf-8") as f:
        json.dump(todos_registros, f, ensure_ascii=False, indent=2)

    print(f"\nExtração concluída: {len(todos_registros)} registros")
    print(f"Arquivo salvo em: {arquivo}")

    return arquivo


if __name__ == "__main__":
    extrair_dados()