# Pipeline de Compras Públicas com Airflow

[![Documentação](https://img.shields.io/badge/docs-site-3f51b5)](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Airflow 3](https://img.shields.io/badge/airflow-3-017CEE)

Todo dia, o governo publica cerca de 1.600 pregões eletrônicos no **PNCP** (Portal Nacional de Contratações Públicas). Este projeto coleta essas contratações automaticamente, grava num banco PostgreSQL, mostra tudo num dashboard e manda por e-mail **só o que interessa a cada pessoa**.

![Dashboard com indicadores e gráficos das contratações](docs/img/dashboard.png)

## O que ele faz

- **Coleta diária:** à meia-noite, uma DAG do Apache Airflow baixa as contratações do dia anterior pela API pública do PNCP, respeitando o limite de requisições.
- **Banco de dados:** as contratações vão para o PostgreSQL sem duplicatas. Processar um dia de novo só atualiza a situação e os valores.
- **Dashboard:** filtros por UF, município, órgão, palavra-chave, valor e prazo, e o link para o edital de cada contratação.
- **Alertas por e-mail:** cada destinatário escolhe palavras-chave, UFs e valor mínimo e recebe só o que bate com isso, com o CSV em anexo.
- **Histórico:** um comando carrega os dias anteriores com o backfill do Airflow.

<img src="docs/img/alerta-email.png" alt="E-mail de alerta com as contratações filtradas" width="600">

## Como funciona

```mermaid
flowchart LR
    API[(API do PNCP)] --> E

    subgraph M["uma vez por modalidade"]
        E[extrair] --> V[validar] --> T[transformar] --> C[carregar]
    end

    C --> DB[(PostgreSQL)]
    DB --> N[notificar] --> EM[e-mails filtrados]
    DB --> D[dashboard]
```

## Começar em um minuto

Com Docker e `make` instalados:

```bash
git clone https://github.com/HenriqueLopes741/pipeline-compras-publicas-airflow.git
cd pipeline-compras-publicas-airflow
make run                # configura, sobe tudo e ativa a DAG
make backfill DIAS=30   # opcional: carrega os últimos 30 dias
```

| Serviço | Endereço |
|---|---|
| Airflow | http://localhost:8080 (usuário `airflow`, senha `airflow`) |
| Dashboard | http://localhost:8501 |
| E-mails de teste (Mailpit) | http://localhost:8025 |

Rode `make` para ver todos os comandos.

## Documentação

O passo a passo completo está no **[site da documentação](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/)**:

- [Instalação](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/instalacao/subir-o-ambiente/): pré-requisitos, primeira execução e backfill
- [Como funciona](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/como-funciona/fluxo/): as tarefas, o agendamento, a API do PNCP e o banco
- [Funções](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/funcoes/parametros/): parâmetros, dados gerados, dashboard e alertas

## Tecnologias

Python 3.12 · Apache Airflow 3 · PostgreSQL 16 · pandas · Streamlit · Docker Compose · pytest · MkDocs

## Licença

[MIT](LICENSE). Os dados são públicos e vêm da [API de consulta do PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html).
