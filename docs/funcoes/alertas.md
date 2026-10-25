# Alertas por e-mail

Um dia de Pregão Eletrônico tem cerca de 1.600 contratações: mandar tudo por e-mail não ajuda ninguém. Os alertas mandam a cada destinatário **só as contratações que batem com os critérios dele**, com o CSV filtrado em anexo.

O envio é feito pela tarefa `notificar`, no fim da DAG, depois que todas as modalidades foram carregadas no banco.

## Configurar os destinatários

Os destinatários ficam em `config/alertas.yml`. Crie o arquivo a partir do modelo e ajuste:

```bash
make alertas
```

O `make alertas` só copia o `config/alertas.exemplo.yml` se o `alertas.yml` ainda não existir: um arquivo já configurado nunca é sobrescrito.

```yaml
destinatarios:
  - email: ti@exemplo.com
    palavras_chave: ["software", "nuvem"]
    ufs: ["DF", "GO"]
    valor_minimo: 50000

  - email: saude@exemplo.com
    palavras_chave: ["medicamento"]
    enviar_se_vazio: true
```

O `alertas.yml` fica fora do Git, porque tem e-mails reais. Mudanças nele valem na próxima execução, sem reiniciar nada.

| Campo | Obrigatório | Padrão | O que faz |
|---|---|---|---|
| `email` | sim | | Endereço do destinatário |
| `palavras_chave` | não | todas | Lista de palavras. Basta **uma** aparecer no objeto |
| `ufs` | não | todas | Lista de siglas de estados |
| `valor_minimo` | não | sem mínimo | Valor estimado mínimo, em reais |
| `enviar_se_vazio` | não | `false` | Envia o e-mail mesmo num dia sem resultados |

Os critérios preenchidos **valem juntos**: no exemplo, `ti@exemplo.com` recebe as contratações com "software" **ou** "nuvem" no objeto, **e** do DF ou de GO, **e** de pelo menos R$ 50 mil. Um destinatário sem nenhum critério recebe todas as contratações do dia.

## Como as palavras-chave são comparadas

- **Sem diferenciar acentos nem maiúsculas.** `computacao` acha "Computação" e `SOFTWARE` acha "software".
- **Pelo começo da palavra.** `software` acha "softwares", mas `ti` não acha "a**ti**vidades". Isso evita que siglas curtas tragam metade do dia.
- **A expressão inteira.** `material de limpeza` só acha esse trecho, com as palavras nessa ordem.

Para pegar variações, liste cada uma: `["medicamento", "remédio", "fármaco"]`.

## Valor mínimo e valor sigiloso

Cerca de 1 em cada 6 contratações tem o valor estimado zerado, em geral porque o orçamento é sigiloso. Com `valor_minimo`, essas contratações **ficam de fora**, porque não dá para saber se passam do mínimo.

Para recebê-las, não use `valor_minimo`.

## O que chega no e-mail

- **Assunto:** `Alerta PNCP 22/10/2026: 12 contratações`
- **Corpo:** os critérios do destinatário e uma tabela com objeto (com link para o edital), órgão, município/UF, valor estimado e prazo de encerramento, das maiores para as menores.
- **Anexo:** `contratacoes-pncp-2026-10-22.csv`, com todas as contratações filtradas e as mesmas colunas do [CSV do pipeline](dados-gerados.md#colunas).

O corpo mostra no máximo as **50 de maior valor**. Quando há mais, o e-mail avisa que a lista completa está no anexo. O limite fica em `LIMITE_NO_EMAIL`, em `src/alertas.py`, e o modelo do e-mail em `src/templates/alerta.html`.

Os alertas usam **todas as contratações do dia no banco**, de todas as modalidades já carregadas, e não só as da execução atual.

## Dia sem resultados

| `enviar_se_vazio` | Nenhuma contratação bateu |
|---|---|
| `false` (padrão) | Não envia nada |
| `true` | Envia um e-mail curto, com o assunto `Alerta PNCP 22/10/2026: nenhuma contratação` e sem anexo |

O `true` serve para quem quer a confirmação diária de que o alerta está funcionando.

## Quando a tarefa roda, pula ou falha

| Situação | `notificar` |
|---|---|
| Todas as modalidades carregadas, ou puladas por falta de dados | Roda |
| Alguma modalidade falhou | Não roda, para não alertar com o dia incompleto |
| Não existe `config/alertas.yml` | Pulada |
| O `alertas.yml` tem um erro | **Falha** antes de enviar qualquer e-mail |

O arquivo é validado inteiro antes do primeiro envio. A mensagem de erro, no log da tarefa, diz a posição do destinatário na lista (contando do 0) e o campo com problema: `destinatarios.1.ufs` é o campo `ufs` do segundo destinatário. Os erros mais comuns:

| Erro | Exemplo |
|---|---|
| Campo com nome errado | `palavra_chave` em vez de `palavras_chave` |
| UF que não existe | `ufs: ["XX"]` |
| E-mail sem `@` ou sem domínio | `email: pessoa.exemplo.com` |
| Valor mínimo negativo | `valor_minimo: -1` |
| Lista de destinatários vazia | `destinatarios: []` |

Um campo com nome errado é erro, e não é ignorado, de propósito: um `palavra_chave` ignorado em silêncio faria a pessoa receber todas as contratações do dia.

## Testar com o Mailpit

O projeto vem com o **Mailpit**, um servidor de e-mail de teste. Ele recebe as mensagens e **não entrega a ninguém**: elas ficam numa caixa de entrada em **http://localhost:8025**, com o corpo e o anexo.

Para testar:

1. Crie o `config/alertas.yml` com `make alertas` (os endereços do exemplo servem).
2. Acione a DAG para um dia que já está no banco: `make rodar DATA=2026-10-20`.
3. Abra http://localhost:8025 e veja um e-mail por destinatário.

Dois destinatários com critérios diferentes recebem e-mails diferentes, da mesma execução.

## Enviar e-mails de verdade

O servidor de e-mail é a conexão `smtp_default`, definida no `docker-compose.yaml` pela variável `AIRFLOW_CONN_SMTP_DEFAULT`. Por padrão, ela aponta para o Mailpit:

```yaml
AIRFLOW_CONN_SMTP_DEFAULT: '{"conn_type": "smtp", "host": "mailpit", "port": 1025, "extra": {"disable_tls": true, "disable_ssl": true, "from_email": "alertas@pncp.local"}}'
```

Para enviar de verdade, troque pelos dados do seu servidor. Com uma conta do Gmail, por exemplo:

```yaml
AIRFLOW_CONN_SMTP_DEFAULT: '{"conn_type": "smtp", "host": "smtp.gmail.com", "port": 587, "login": "voce@gmail.com", "password": "SENHA_DE_APP", "extra": {"disable_ssl": true, "from_email": "voce@gmail.com"}}'
```

| Campo | O que é |
|---|---|
| `host` e `port` | Endereço do servidor SMTP. Em geral, porta `587` (STARTTLS) ou `465` (SSL) |
| `login` e `password` | Usuário e senha do servidor. No Gmail, use uma [senha de app](https://support.google.com/accounts/answer/185833), e não a senha da conta |
| `disable_ssl` | `true` na porta 587, que começa sem criptografia e passa a usar TLS; `false` na porta 465 |
| `disable_tls` | `true` só para servidores sem criptografia, como o Mailpit |
| `from_email` | O remetente que aparece no e-mail |

Depois de mudar, rode `make run`: ele recria os containers do Airflow, que passam a ler a variável nova.

> **Não faça commit da senha.** O `docker-compose.yaml` é versionado. Desfaça a mudança antes de um commit, ou mantenha a versão com a senha só na sua máquina.

Uma conexão `smtp_default` criada na tela de conexões do Airflow **não tem efeito**: a variável de ambiente tem prioridade sobre ela.
