import pendulum
from airflow.sdk import Param, dag, task, task_group

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
    # Se a máquina estava suspensa, a execução atrasada dispara logo ao
    # acordar, antes da rede voltar: tentar de novo em vez de falhar
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=5),
    },
    # Aparecem como formulário ao acionar a DAG manualmente; a execução
    # agendada usa os valores padrão
    params={
        "modalidades": Param(
            [6],
            type="array",
            items={"type": "integer"},
            minItems=1,
            title="Modalidades",
            description="Códigos das modalidades de contratação (6 = Pregão Eletrônico)",
        ),
        "data": Param(
            None,
            type=["null", "string"],
            format="date",
            title="Data",
            description="Dia a processar. Vazio: dia anterior à execução",
        ),
    },
    tags=["pncp", "etl", "pipeline"]
)
def pncp_pipeline():

    @task
    def listar_modalidades(params=None):
        """
        Tarefa responsável por entregar a lista de modalidades ao mapeamento.
        """
        return params["modalidades"]

    @task_group
    def processar_modalidade(modalidade):

        # Uma modalidade por vez, para não estourar o limite de requisições da API
        @task(max_active_tis_per_dag=1)
        def extrair_pncp(modalidade, params=None, data_interval_end=None):
            """
            Tarefa responsável por extrair os dados do PNCP de uma modalidade.
            """
            from src.extract import extrair_dados

            if params["data"]:
                dia = pendulum.parse(params["data"]).strftime("%Y%m%d")
            else:
                # No Airflow 3 o @daily não tem intervalo: data_interval_end é o
                # momento da execução, então o dia completo mais recente é o anterior
                dia = (
                    data_interval_end.in_timezone(FUSO)
                    .subtract(days=1)
                    .strftime("%Y%m%d")
                )

            arquivo = extrair_dados(
                data_inicial=dia,
                data_final=dia,
                modalidade=modalidade,
            )

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

        extracao = extrair_pncp(modalidade)
        validacao = validar_dados(extracao)
        transformar_pncp(validacao)

    processar_modalidade.expand(modalidade=listar_modalidades())
pncp_pipeline()
