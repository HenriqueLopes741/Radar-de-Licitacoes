from datetime import datetime

import pendulum 
from airflow.sdk import dag, task

@dag(
    dag_id="pncp_pipeline",
    description="Pipeline de extração e transformação de dados do PNCP",
    schedule=None, 
    start_date=pendulum.datetime(
        2026, 10, 13, tz="America/Sao_Paulo"
    ),
    catchup=False,
    tags=["pncp", "etl", "pipeline"]
)
def pncp_pipeline():

    @task
    def extrair_pncp():
        """
        Tarefa responsável por extrair os dados do PNCP.
        """
        from src.extract import extrair_dados

        extrair_dados()

    @task
    def validar_dados():
        """
        Tarefa responsável por validar os dados extraídos.
        """

        import json 
        from pathlib import Path

        arquivo = Path("/opt/airflow/data/raw/contratacoes.json")

        if not arquivo.exists():
            raise FileNotFoundError(
                f"JSON não encontrado: {arquivo}"
            )

        with open(arquivo, "r", encoding="utf-8") as f:
            registros = json.load(f)

        if not isinstance(registros, list):
            raise ValueError(
                f"A extração não gerou uma lista com registros"
            )
        print(f"Registros encontrados: {len(registros)}")

    @task
    def transformar_pncp():
        """
        Tarefa responsável por transformar os dados extraídos.
        """
        from src.transform import transformar_dados

        transformar_dados()

    extracao = extrair_pncp()
    validacao = validar_dados()
    transformacao = transformar_pncp()

    extracao >> validacao >> transformacao

pncp_pipeline()