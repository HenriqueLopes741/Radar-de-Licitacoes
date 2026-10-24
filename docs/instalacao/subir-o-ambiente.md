# Subir o ambiente

Esta página leva de uma pasta vazia até a primeira carga no banco. Leva uns 15 minutos, contando o download das imagens do Docker.

## Pré-requisitos

- **Docker** e **Docker Compose v2** (o comando é `docker compose`, sem hífen)
- Pelo menos **4 GB de RAM** livres para o Docker
- **Python 3**, só para gerar a chave de criptografia do `.env`
- As portas **8080**, **8501**, **8025** e **5433** livres na máquina

## 1. Baixar o projeto

```bash
git clone https://github.com/HenriqueLopes741/pipeline-compras-publicas-airflow.git
cd pipeline-compras-publicas-airflow
```

## 2. Criar as pastas e o `.env`

```bash
mkdir -p logs plugins config data
echo "AIRFLOW_UID=$(id -u)" > .env
echo "FERNET_KEY=$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" >> .env
```

- `AIRFLOW_UID` faz os containers gravarem em `data/` e `logs/` com o seu usuário. Sem ele, os arquivos ficam com outro dono e você não consegue apagá-los sem `sudo`.
- `FERNET_KEY` é a chave que o Airflow usa para criptografar as senhas das conexões guardadas no banco.

O `.env` fica fora do Git.

## 3. Configurar os alertas (opcional)

Para receber os e-mails, copie o modelo e troque os endereços:

```bash
cp config/alertas.exemplo.yml config/alertas.yml
```

Sem esse arquivo, o pipeline roda normalmente e só pula a tarefa de envio. Os campos estão explicados em [Alertas por e-mail](../funcoes/alertas.md).

## 4. Inicializar o Airflow

```bash
docker compose up airflow-init
```

Só precisa rodar na primeira vez. O comando cria as tabelas internas do Airflow e o usuário de acesso. Na mesma subida, o Postgres cria os bancos `pncp` (dados do pipeline) e `pncp_teste` (usado pelos testes).

Espere a mensagem `airflow-init-1 exited with code 0`.

## 5. Subir os serviços

```bash
docker compose up -d
```

Na primeira vez, o Docker também monta a imagem do dashboard. Para ver se tudo subiu:

```bash
docker compose ps
```

Todos os serviços devem aparecer como `healthy`. O Airflow leva cerca de 1 minuto para ficar pronto.

| Serviço | Endereço | Acesso |
|---|---|---|
| Airflow | http://localhost:8080 | usuário `airflow`, senha `airflow` |
| Dashboard | http://localhost:8501 | sem login |
| Mailpit (e-mails de teste) | http://localhost:8025 | sem login |
| PostgreSQL | `localhost:5433` | usuário `airflow`, senha `airflow` |

O dashboard, o Mailpit e o Postgres só aceitam conexões da própria máquina.

## 6. Ativar a DAG

1. Entre em **http://localhost:8080**.
2. Na lista de DAGs, procure a `pncp_pipeline`. Ela começa **pausada**.
3. Clique no botão ao lado do nome para ativá-la.

Logo ao ser ativada, a DAG processa o **dia anterior**. Depois disso, ela roda sozinha todo dia à meia-noite, horário de Brasília. O motivo está em [Agendamento](../como-funciona/agendamento.md).

> **A DAG não aparece?** O Airflow lê a pasta `dags/` a cada poucos segundos, mas a primeira leitura pode levar até 1 minuto. Se demorar mais, procure um aviso de erro de importação no topo da lista de DAGs.

## 7. Acompanhar a primeira execução

Clique em `pncp_pipeline` para abrir a grade de execuções. A extração leva cerca de **3 minutos**, por causa do limite de requisições da API do PNCP. As outras tarefas levam segundos.

Quando a execução ficar verde:

- os arquivos do dia aparecem em `data/raw/` e `data/processed/`;
- o dashboard em **http://localhost:8501** passa a mostrar os dados (recarregue a página);
- se você configurou os alertas, os e-mails aparecem no Mailpit em **http://localhost:8025**.

Para conferir direto no banco:

```bash
docker compose exec postgres psql -U airflow -d pncp -c \
  "SELECT data_publicacao::date AS dia, count(*) FROM contratacoes GROUP BY 1 ORDER BY 1"
```

## 8. Trazer o histórico

O banco começa só com o dia anterior. Para carregar os últimos 30 dias, por exemplo, siga [Carregar dias anteriores](carregar-dias-anteriores.md).

## Parar e atualizar

```bash
docker compose down        # para os serviços; os dados continuam no volume
docker compose up -d       # sobe de novo
```

> **Cuidado com o `docker compose down -v`.** O `-v` apaga o volume do Postgres, onde ficam o banco do Airflow **e** o banco `pncp` com todas as contratações. Na próxima subida é preciso rodar o `airflow-init` de novo e recarregar o histórico.

As pastas `dags/`, `src/` e `config/` são compartilhadas com os containers: mudanças no código da DAG, das tarefas ou no `alertas.yml` valem na próxima execução, sem reiniciar nada. O dashboard é a exceção, porque o código vai dentro da imagem:

```bash
docker compose up -d --build dashboard
```

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `port is already allocated` ao subir | Outro programa usa a porta | Pare o outro programa ou troque a porta da esquerda em `ports:` no `docker-compose.yaml` |
| `Permission denied` ao apagar arquivos de `data/` | `.env` sem `AIRFLOW_UID` | Refaça o passo 2 e suba de novo |
| `database "pncp" does not exist` na tarefa `carregar_banco` | O volume do Postgres já existia antes do projeto criar o banco `pncp` | `docker compose exec postgres psql -U airflow -c "CREATE DATABASE pncp"` |
| Dashboard diz "Ainda não há dados" | A primeira carga ainda não terminou | Espere a execução ficar verde e recarregue |
