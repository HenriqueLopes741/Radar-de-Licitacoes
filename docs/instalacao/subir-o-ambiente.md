# Subir o ambiente

Esta página leva de uma pasta vazia até a primeira carga no banco. Leva uns 15 minutos, contando o download das imagens do Docker.

## Pré-requisitos

- **Docker** e **Docker Compose v2** (o comando é `docker compose`, sem hífen)
- **make** e **openssl**, que já vêm no Linux e no macOS. No Windows, use o [WSL](https://learn.microsoft.com/pt-br/windows/wsl/install)
- Pelo menos **4 GB de RAM** livres para o Docker
- As portas **8080**, **8501**, **8025** e **5433** livres na máquina

## Subir com um comando

```bash
git clone https://github.com/HenriqueLopes741/pipeline-compras-publicas-airflow.git
cd pipeline-compras-publicas-airflow
make run
```

O `make run` faz tudo o que falta, na ordem:

1. Cria as pastas `logs/`, `plugins/`, `config/` e `data/`.
2. Cria o `.env`, **só se ele ainda não existir**, com:
    - `AIRFLOW_UID`: faz os containers gravarem em `data/` e `logs/` com o seu usuário. Sem ele, os arquivos ficam com outro dono e você não consegue apagá-los sem `sudo`;
    - `FERNET_KEY`: a chave que o Airflow usa para criptografar as senhas das conexões guardadas no banco.
3. Sobe todos os serviços e **espera ficarem prontos**. Na primeira vez, isso inclui criar as tabelas do Airflow, o usuário de acesso e os bancos `pncp` e `pncp_teste`, e montar a imagem do dashboard.
4. **Ativa a DAG** `pncp_pipeline`.
5. Mostra os endereços:

| Serviço | Endereço | Acesso |
|---|---|---|
| Airflow | http://localhost:8080 | usuário `airflow`, senha `airflow` |
| Dashboard | http://localhost:8501 | sem login |
| Mailpit (e-mails de teste) | http://localhost:8025 | sem login |
| PostgreSQL | `localhost:5433` | usuário `airflow`, senha `airflow` |

O dashboard, o Mailpit e o Postgres só aceitam conexões da própria máquina.

Pode rodar o `make run` quantas vezes quiser: ele não sobrescreve o `.env` nem o `config/alertas.yml`, e só recria os containers que mudaram. Ele também **ativa a DAG toda vez**: se você a pausou na tela do Airflow, o `make run` a ativa de novo.

Para ver todos os comandos, rode só `make`.

## Configurar os alertas (opcional)

Para receber os e-mails, crie o arquivo de destinatários a partir do modelo e troque os endereços:

```bash
make alertas
```

Sem esse arquivo, o pipeline roda normalmente e só pula a tarefa de envio. Os campos estão explicados em [Alertas por e-mail](../funcoes/alertas.md).

## A primeira execução

Logo ao ser ativada, a DAG processa o **dia anterior**. Depois disso, ela roda sozinha todo dia à meia-noite, horário de Brasília. O motivo está em [Agendamento](../como-funciona/agendamento.md).

Em http://localhost:8080, clique em `pncp_pipeline` para abrir a grade de execuções. A extração leva cerca de **3 minutos**, por causa do limite de requisições da API do PNCP. As outras tarefas levam segundos.

Quando a execução ficar verde:

- os arquivos do dia aparecem em `data/raw/` e `data/processed/`;
- o dashboard em **http://localhost:8501** passa a mostrar os dados (recarregue a página);
- se você configurou os alertas, os e-mails aparecem no Mailpit em **http://localhost:8025**.

Para conferir direto no banco, `make psql` abre o terminal do banco `pncp`:

```sql
SELECT data_publicacao::date AS dia, count(*) FROM contratacoes GROUP BY 1 ORDER BY 1;
```

## Trazer o histórico

O banco começa só com o dia anterior. Para carregar os últimos 30 dias:

```bash
make backfill DIAS=30
```

Os detalhes e o tempo de cada período estão em [Carregar dias anteriores](carregar-dias-anteriores.md).

## Parar e atualizar

```bash
make stop      # para os serviços; os dados continuam no volume
make run       # sobe de novo
make ps        # situação dos serviços
make logs      # acompanha os logs (S=airflow-worker para um serviço só)
```

> **Cuidado com o `make limpar`.** Ele roda `docker compose down -v`, que apaga o volume do Postgres, onde ficam o banco do Airflow **e** o banco `pncp` com todas as contratações. Por isso pede que você digite `apagar` para confirmar. Depois dele, o próximo `make run` começa do zero.

As pastas `dags/`, `src/` e `config/` são compartilhadas com os containers: mudanças no código da DAG, das tarefas ou no `alertas.yml` valem na próxima execução, sem reiniciar nada. O dashboard é a exceção, porque o código vai dentro da imagem:

```bash
docker compose up -d --build dashboard
```

## Sem o make

Os mesmos passos, à mão:

```bash
mkdir -p logs plugins config data
echo "AIRFLOW_UID=$(id -u)" > .env
echo "FERNET_KEY=$(openssl rand -base64 32 | tr '+/' '-_')" >> .env

docker compose up -d --wait
docker compose exec airflow-scheduler airflow dags unpause pncp_pipeline
```

Se o último comando disser `No paused DAGs were found` logo na primeira subida, o Airflow ainda não leu a pasta `dags/`: espere alguns segundos e rode de novo. Para parar, `docker compose down`.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `port is already allocated` ao subir | Outro programa usa a porta | Pare o outro programa ou troque a porta da esquerda em `ports:` no `docker-compose.yaml` |
| `Permission denied` ao apagar arquivos de `data/` | `.env` sem `AIRFLOW_UID` | Acrescente a linha com `echo "AIRFLOW_UID=$(id -u)" >> .env`, rode `make run` e corrija o dono dos arquivos antigos com `sudo chown -R $(id -u) data logs`. Não apague o `.env`: uma `FERNET_KEY` nova não abre o que foi criptografado com a antiga |
| `A DAG pncp_pipeline não apareceu no Airflow em 1 minuto` | Erro ao importar a DAG | Veja o aviso de erro de importação no topo da lista de DAGs em http://localhost:8080 |
| `database "pncp" does not exist` na tarefa `carregar_banco` | O volume do Postgres já existia antes do projeto criar o banco `pncp` | `docker compose exec postgres psql -U airflow -c "CREATE DATABASE pncp"` |
| Dashboard diz "Ainda não há dados" | A primeira carga ainda não terminou | Espere a execução ficar verde e recarregue |
