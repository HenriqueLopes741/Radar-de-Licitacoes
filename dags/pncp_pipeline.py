import pendulum
from airflow.sdk import CronDataIntervalTimetable, Param, dag, task, task_group

FUSO = "America/Sao_Paulo"


@dag(
    dag_id="pncp_pipeline",
    description="Coleta as contratações do dia no PNCP, grava no banco e envia os alertas",
    # Cada execução cobre um dia inteiro e roda à meia-noite (horário de
    # Brasília) seguinte. Assim, a data de um backfill é o dia processado
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone=FUSO),
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
        def extrair_pncp(modalidade, params=None, data_interval_start=None):
            """
            Tarefa responsável por extrair os dados do PNCP de uma modalidade.
            """
            from src.extract import dia_a_processar, extrair_dados

            dia = dia_a_processar(params["data"], data_interval_start)

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

        @task
        def carregar_banco(arquivo):
            """
            Tarefa responsável por carregar os dados transformados no banco.
            """
            from airflow.providers.postgres.hooks.postgres import PostgresHook

            from src.load import carregar_dados

            conexao = PostgresHook(postgres_conn_id="pncp_db").get_conn()

            try:
                carregar_dados(arquivo_csv=arquivo, conexao=conexao)
            finally:
                conexao.close()

        extracao = extrair_pncp(modalidade)
        validacao = validar_dados(extracao)
        transformacao = transformar_pncp(validacao)
        carregar_banco(transformacao)

    # Roda mesmo se alguma modalidade foi pulada (dia sem contratações);
    # só não roda se alguma falhou, para não alertar com o dia incompleto
    @task(trigger_rule="none_failed")
    def notificar(params=None, data_interval_start=None):
        """
        Tarefa responsável por enviar os alertas por e-mail a cada destinatário.
        """
        import tempfile
        from datetime import datetime
        from pathlib import Path

        from airflow.providers.postgres.hooks.postgres import PostgresHook
        from airflow.providers.smtp.hooks.smtp import SmtpHook
        from airflow.sdk.exceptions import AirflowSkipException

        from src.alertas import carregar_config, contratacoes_do_dia, enviar_alertas
        from src.extract import dia_a_processar

        arquivo_config = Path("config/alertas.yml")
        if not arquivo_config.exists():
            raise AirflowSkipException(f"Nenhum alerta configurado em {arquivo_config}")

        # Valida antes de tudo: um YAML errado falha aqui, sem enviar nada
        config = carregar_config(arquivo_config)

        dia = datetime.strptime(
            dia_a_processar(params["data"], data_interval_start), "%Y%m%d"
        ).date()

        conexao = PostgresHook(postgres_conn_id="pncp_db").get_conn()
        try:
            contratacoes = contratacoes_do_dia(conexao, dia)
        finally:
            conexao.close()

        # O "with" abre a conexão com o servidor de e-mail e a fecha no fim
        with SmtpHook(smtp_conn_id="smtp_default") as smtp, tempfile.TemporaryDirectory() as pasta:
            enviados = enviar_alertas(
                config, contratacoes, dia, pasta, smtp.send_email_smtp
            )

        print(f"Alertas enviados: {len(enviados)} de {len(config.destinatarios)}")

    processar_modalidade.expand(modalidade=listar_modalidades()) >> notificar()

pncp_pipeline()
