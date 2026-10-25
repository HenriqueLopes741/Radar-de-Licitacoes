# Comandos do dia a dia. "make" sozinho lista todos.
.DEFAULT_GOAL := help
.PHONY: help run stop ps logs ativar rodar backfill alertas psql test docs limpar

COMPOSE := docker compose
# -T: sem terminal interativo, para funcionar também em scripts e no CI
AIRFLOW := $(COMPOSE) exec -T airflow-scheduler airflow
DAG := pncp_pipeline

# Só com a data, o Airflow considera meia-noite em UTC (21h do dia anterior
# em Brasília) e o último dia do backfill fica de fora
FUSO := -03:00

# Datas no horário de Brasília. "date -d" é do Linux; "date -v", do macOS
ONTEM := $(shell TZ=America/Sao_Paulo date -d "-1 day" +%F 2>/dev/null || TZ=America/Sao_Paulo date -v-1d +%F)

# DIAS=30: de 30 dias atrás até ontem
ifdef DIAS
INICIO := $(shell TZ=America/Sao_Paulo date -d "-$(DIAS) days" +%F 2>/dev/null || TZ=America/Sao_Paulo date -v-$(DIAS)d +%F)
FIM := $(ONTEM)
endif

# Acionada pelo CLI, a execução não tem intervalo de dados e a DAG não saberia
# qual dia processar: sem DATA, vai o dia anterior, como na execução agendada
DATA ?= $(ONTEM)

# Vírgula literal dentro de $(if ...), que usa a vírgula para separar os argumentos
virgula := ,
# {"modalidades": [6,8], "data": "2026-10-20"}, só com o que foi informado
CONF = {$(if $(MODALIDADES),"modalidades": [$(MODALIDADES)])$(if $(and $(MODALIDADES),$(DATA)),$(virgula) )$(if $(DATA),"data": "$(DATA)")}

# "=" e não ":=": só lê o arquivo quando o make docs roda
VERSAO_MKDOCS = $(shell sed -n 's/^mkdocs-material==//p' requirements-docs.txt)

help: ## Lista os comandos
	@echo "Uso: make <comando>"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} /^[a-z]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: .env ## Configura o que faltar, sobe o ambiente e ativa a DAG
	@mkdir -p logs plugins config data
	@# --wait: só devolve o terminal com todos os serviços prontos.
	@# O airflow-init roda antes dos serviços do Airflow, pelo depends_on
	$(COMPOSE) up -d --wait
	@$(MAKE) --no-print-directory ativar
	@echo ""
	@echo "Ambiente no ar:"
	@echo "  Airflow    http://localhost:8080  (usuário airflow, senha airflow)"
	@echo "  Dashboard  http://localhost:8501"
	@echo "  Mailpit    http://localhost:8025"
	@echo "  Postgres   localhost:5433         (banco pncp, usuário airflow, senha airflow)"

# Só roda se o .env não existir: um .env já configurado nunca é sobrescrito.
# A FERNET_KEY é base64 "urlsafe" de 32 bytes: o tr troca + e / por - e _
.env:
	@echo "AIRFLOW_UID=$$(id -u)" > $@
	@echo "FERNET_KEY=$$(openssl rand -base64 32 | tr '+/' '-_')" >> $@
	@echo "Criado o .env"

stop: ## Para os serviços, mantendo os dados
	$(COMPOSE) down

ps: ## Mostra a situação dos serviços
	$(COMPOSE) ps

logs: ## Acompanha os logs (S=airflow-worker para um serviço só)
	$(COMPOSE) logs -f --tail=100 $(S)

# Logo depois do primeiro "up", o Airflow pode ainda não ter lido a pasta
# dags/: espera a DAG aparecer por até 1 minuto. O "details" é quem diz se ela
# existe, porque o "unpause" termina sem erro mesmo para uma DAG que não existe
ativar: ## Ativa a DAG pncp_pipeline
	@# Cada chamada do CLI do Airflow leva uns 4s: 15 tentativas dão cerca de 1 minuto
	@for tentativa in $$(seq 1 15); do \
		if $(AIRFLOW) dags details $(DAG) >/dev/null 2>&1; then \
			$(AIRFLOW) dags unpause $(DAG) >/dev/null 2>&1 && echo "DAG $(DAG) ativada"; exit; \
		fi; \
		sleep 1; \
	done; \
	echo "A DAG $(DAG) não apareceu no Airflow em 1 minuto. Veja os erros de importação em http://localhost:8080" >&2; \
	exit 1

rodar: ## Aciona a DAG agora (DATA=2026-10-20 MODALIDADES=6,8; sem DATA: ontem; sem MODALIDADES: 6)
	$(AIRFLOW) dags trigger $(DAG) --conf '$(CONF)'

backfill: ## Carrega vários dias (INICIO=2026-10-01 FIM=2026-10-10 ou DIAS=30; opcionais: MODALIDADES, REPROCESSAR, SIMULAR=1)
	@if [ -z "$(INICIO)" ] || [ -z "$(FIM)" ]; then \
		echo "Informe INICIO e FIM (AAAA-MM-DD) ou DIAS. Exemplo: make backfill DIAS=30" >&2; exit 1; \
	fi
	$(AIRFLOW) backfill create --dag-id $(DAG) \
		--from-date $(INICIO)T00:00:00$(FUSO) \
		--to-date $(FIM)T00:00:00$(FUSO) \
		$(if $(MODALIDADES),--dag-run-conf '{"modalidades": [$(MODALIDADES)]}') \
		$(if $(REPROCESSAR),--reprocess-behavior $(REPROCESSAR)) \
		$(if $(SIMULAR),--dry-run)

alertas: ## Cria o config/alertas.yml a partir do modelo, se ainda não existir
	@if [ -e config/alertas.yml ]; then \
		echo "config/alertas.yml já existe; nada foi alterado"; \
	else \
		cp config/alertas.exemplo.yml config/alertas.yml; \
		echo "Criado config/alertas.yml: troque os e-mails do exemplo pelos seus"; \
	fi

psql: ## Abre o psql no banco pncp
	$(COMPOSE) exec postgres psql -U airflow -d pncp

test: ## Roda os testes (precisa do ambiente Python, veja a documentação)
	pytest

docs: ## Serve a documentação em http://localhost:8000 (Ctrl+C para parar)
	docker run --rm -it -p 127.0.0.1:8000:8000 -v "$(CURDIR)":/docs squidfunk/mkdocs-material:$(VERSAO_MKDOCS)

limpar: ## Para tudo e APAGA os bancos do Airflow e do pncp (pede confirmação)
	@printf "Isso apaga o banco do Airflow e todas as contratações do banco pncp.\nDigite apagar para confirmar: "; \
	read resposta; \
	if [ "$$resposta" = "apagar" ]; then \
		$(COMPOSE) down -v; \
	else \
		echo "Nada foi apagado."; \
	fi
