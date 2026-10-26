# Pipeline de Compras Públicas com Airflow

[![Documentação](https://img.shields.io/badge/docs-site-3f51b5)](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Airflow 3](https://img.shields.io/badge/airflow-3-017CEE)

Coleta todo dia as contratações publicadas no **PNCP**, grava num PostgreSQL, mostra num dashboard e manda por e-mail **só o que interessa a cada pessoa**, filtrado por palavras-chave, estados e valor mínimo.

<table>
  <tr>
    <td width="60%"><img src="docs/img/dashboard.png" alt="Dashboard com indicadores e gráficos das contratações"></td>
    <td width="40%"><img src="docs/img/alerta-email.png" alt="E-mail de alerta com as contratações filtradas"></td>
  </tr>
</table>

## Como usar

Com Docker e `make`:

```bash
git clone https://github.com/HenriqueLopes741/pipeline-compras-publicas-airflow.git
cd pipeline-compras-publicas-airflow
make run                # configura, sobe tudo e ativa a coleta diária
make backfill DIAS=30   # opcional: carrega os últimos 30 dias
```

Airflow em http://localhost:8080 (`airflow`/`airflow`) e dashboard em http://localhost:8501.

**[Documentação completa →](https://henriquelopes741.github.io/pipeline-compras-publicas-airflow/)**

## Licença

[MIT](LICENSE). Dados públicos da [API do PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html).
