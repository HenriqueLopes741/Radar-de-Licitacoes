import pendulum
from airflow.sdk import dag, task

FUSO = "America/Sao_Paulo"


@dag(
    dag_id="pncp_pipeline",
    description="Pipeline de extração e transformação de dados do PNCP",
    # Roda à meia-noite (horário de Brasília) e processa o dia anterior
    schedule="@daily",
    start_date=pendulum.datetime(
        2026, 10, 13, tz=FUSO
    ),
    catchup=False,
    tags=["pncp", "etl", "pipeline"]
)
def pncp_pipeline():

    @task
    def extrair_pncp(data_interval_end=None):
        """
        Tarefa responsável por extrair os dados do PNCP do dia anterior à execução.
        """
        from src.extract import extrair_dados

        # No Airflow 3 o @daily não tem intervalo: data_interval_end é o
        # momento da execução, então o dia completo mais recente é o anterior
        dia = (
            data_interval_end.in_timezone(FUSO)
            .subtract(days=1)
            .strftime("%Y%m%d")
        )
        arquivo = extrair_dados(data_inicial=dia, data_final=dia)

        return str(arquivo)

    @task
    def validar_dados(arquivo):
        """
        Tarefa responsável por validar os dados extraídos.
        """

        import json
        from pathlib import Path

        from airflow.sdk.exceptions import AirflowSkipException

        arquivo = Path(arquivo)

        if not arquivo.exists():
            raise FileNotFoundError(
                f"JSON não encontrado: {arquivo}"
            )

        with open(arquivo, "r", encoding="utf-8") as f:
            registros = json.load(f)

        if not isinstance(registros, list):
            raise ValueError(
                "A extração não gerou uma lista com registros"
            )

        # Dia sem contratações: pula a transformação em vez de falhar
        if not registros:
            raise AirflowSkipException(
                f"Nenhuma contratação em {arquivo.name}"
            )

        print(f"Registros encontrados: {len(registros)}")

        return str(arquivo)

    @task
    def transformar_pncp(arquivo):
        """
        Tarefa responsável por transformar os dados extraídos.
        """
        from pathlib import Path

        from src.transform import transformar_dados

        arquivo = Path(arquivo)
        saida = Path("data/processed") / f"{arquivo.stem}.csv"

        transformar_dados(arquivo_entrada=arquivo, arquivo_saida=saida)

        return str(saida)

    extracao = extrair_pncp()
    validacao = validar_dados(extracao)
    transformar_pncp(validacao)

pncp_pipeline()
