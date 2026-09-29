# Guia de Configuração e Execução

Este documento descreve como configurar, executar e validar o projeto **Pipeline de Monitoramento e Detecção de Tendências em Tecnologia a partir do Hacker News** em um novo ambiente Databricks.

O projeto pode ser inicializado de duas formas:

1. **Parte 1 — Configuração automática utilizando `databricks.yml`**  
   Método recomendado. O Databricks Declarative Automation Bundle cria automaticamente os principais recursos do projeto.

2. **Parte 2 — Configuração manual**  
   Deve ser utilizada caso o Bundle não funcione corretamente no workspace ou algum recurso não possa ser criado automaticamente.

> Não é necessário executar os dois métodos. Utilize primeiro a Parte 1. A Parte 2 funciona como procedimento de contingência.

---

# Pré-requisitos

Antes de iniciar, é necessário:

- acesso a um workspace Databricks;
- Unity Catalog habilitado;
- permissão para criar Catalog, Schema, Volume, Pipeline, Job, SQL Warehouse e Databricks App;
- acesso ao GitHub;
- acesso ao repositório do projeto.

Repositório oficial:

`https://github.com/Andre2217/ProjetoFinalEngDados`

A estrutura principal esperada é:

```text
ProjetoFinalEngDados/
│
├── databricks.yml
├── requirements.txt
├── README.md
├── RUNBOOK.md
│
├── notebooks/
│   ├── 00_setup.sql
│   ├── 01_landing.py
│   ├── 02_landing_to_bronze.py
│   ├── 03_quality_report.sql
│   ├── 04_bronze_to_silver.py
│   └── 05_silver_to_gold.py
│
└── arquivos da aplicação Streamlit
```

---

# PARTE 1 — CONFIGURAÇÃO AUTOMÁTICA COM `databricks.yml`

## 1. Conectar o repositório ao Databricks

No Databricks, acesse:

```text
Workspace
→ Create
→ Git folder
```

Informe o repositório:

```text
https://github.com/Andre2217/ProjetoFinalEngDados
```

Utilize a branch:

```text
main
```

Após a criação, confirme que o arquivo abaixo está disponível na raiz do projeto:

```text
databricks.yml
```

---

# 2. Implantar o Bundle

Abra o arquivo:

```text
databricks.yml
```

No editor do Databricks, localize o painel:

```text
Deployments
```

Selecione o target:

```text
default
```

Clique em:

```text
Deploy
```

O Databricks primeiro validará o Bundle.

Revise a lista de recursos que serão criados e confirme novamente em:

```text
Deploy
```

Acompanhe a execução através da janela:

```text
Project output
```

O deploy deve finalizar sem erros.

---

## 2.1. Alternativa utilizando Databricks CLI

Caso o Bundle esteja sendo executado através de terminal, entre na pasta do projeto e execute:

```bash
databricks bundle validate -t default
```

Se a validação finalizar corretamente:

```bash
databricks bundle deploy -t default
```

Para executar o Job criado pelo Bundle:

```bash
databricks bundle run hacker_news_pipeline -t default
```

O método pela interface do Databricks é suficiente para a utilização normal deste projeto.

---

# 3. Recursos que devem ser criados pelo Bundle

Após o deploy, devem existir os seguintes recursos:

| Recurso | Nome |
|---|---|
| Catalog | `hackernews` |
| Schema | `hacker_news` |
| Volume | `data` |
| SQL Warehouse | `Hacker News SQL Warehouse` |
| ETL Pipeline | `Hacker News - Medallion Pipeline` |
| Lakeflow Job | `Hacker News Pipeline` |
| Databricks App | `hackernews` |

Além disso, o Job deve possuir as tasks:

```text
landing
↓
medallion_pipeline
```

O Job deve estar configurado para execução:

```text
a cada 30 minutos
```

---

# 4. Validar Catalog, Schema e Volume

Acesse:

```text
Catalog
→ Catalog Explorer
→ hackernews
→ hacker_news
```

Confirme a existência do Volume:

```text
Volumes
→ data
```

A estrutura esperada é:

```text
hackernews
└── hacker_news
    └── Volumes
        └── data
```

O caminho utilizado pela Landing será:

```text
/Volumes/hackernews/hacker_news/data/landing
```

---

# 5. Validar o SQL Warehouse

Acesse:

```text
SQL
→ SQL Warehouses
```

Confirme a existência de:

```text
Hacker News SQL Warehouse
```

A configuração criada pelo Bundle deve utilizar SQL Warehouse Serverless quando essa funcionalidade estiver disponível no workspace.

O Warehouse será utilizado principalmente pelo Databricks App para realizar consultas SQL sobre as tabelas da camada Gold.

---

# 6. Validar o ETL Pipeline

Acesse:

```text
Jobs & Pipelines
→ Pipelines
```

Abra:

```text
Hacker News - Medallion Pipeline
```

Confirme que o destino padrão está configurado como:

```text
Catalog: hackernews
Schema: hacker_news
```

Confirme também que os seguintes códigos fazem parte da Pipeline:

```text
notebooks/02_landing_to_bronze.py
notebooks/04_bronze_to_silver.py
notebooks/05_silver_to_gold.py
```

O Pipeline deve representar o fluxo:

```text
Landing
↓
Bronze
↓
Silver
↓
Gold
```

O processamento da Landing utiliza Auto Loader e mantém o controle dos arquivos que já foram processados.

---

# 7. Validar o Event Log

Após a primeira execução do Pipeline, acesse:

```text
Catalog Explorer
→ hackernews
→ hacker_news
```

Deve existir:

```text
pipeline_event_log
```

Nome completo:

```text
hackernews.hacker_news.pipeline_event_log
```

Esse Event Log registra informações de execução, métricas e expectativas de qualidade do Lakeflow Pipeline.

---

# 8. Validar o Lakeflow Job

Acesse:

```text
Jobs & Pipelines
→ Jobs
```

Abra:

```text
Hacker News Pipeline
```

O Job deve possuir duas tasks.

## Task 1 — Landing

```text
Nome: landing
Tipo: Notebook
Notebook: notebooks/01_landing
Git branch: main
```

Essa task consulta a API oficial do Hacker News e cria um novo snapshot NDJSON.

---

## Task 2 — Medallion Pipeline

```text
Nome: medallion_pipeline
Tipo: Pipeline
Pipeline: Hacker News - Medallion Pipeline
```

Dependência:

```text
landing
↓
medallion_pipeline
```

A segunda task somente deve executar quando a task `landing` terminar com sucesso.

---

# 9. Validar o agendamento

Dentro do Job:

```text
Hacker News Pipeline
```

acesse:

```text
Schedules & Triggers
```

Confirme que existe um agendamento ativo para:

```text
a cada 30 minutos
```

O comportamento esperado é aproximadamente:

```text
00:00
00:30
01:00
01:30
02:00
02:30
...
```

O timezone configurado pelo projeto é:

```text
America/Fortaleza
```

---

# 10. Validar o Databricks App

Acesse:

```text
Apps
```

Abra:

```text
hackernews
```

Confirme:

```text
Git repository:
https://github.com/Andre2217/ProjetoFinalEngDados

Branch:
main
```

O App deve possuir acesso ao:

```text
Hacker News SQL Warehouse
```

com permissão:

```text
CAN USE
```

Se o App tiver sido criado, mas ainda não estiver executando, abra sua página e utilize:

```text
Deploy
```

ou:

```text
Start
```

conforme as opções apresentadas pelo workspace.

Após iniciar, acesse o link disponibilizado pelo próprio Databricks App e confirme que o dashboard é carregado.

---

# 11. Primeira execução completa

Após verificar todos os recursos, execute manualmente o Job uma vez antes de depender apenas do agendamento automático.

Acesse:

```text
Jobs & Pipelines
→ Jobs
→ Hacker News Pipeline
```

Clique em:

```text
Run now
```

O fluxo esperado é:

```text
Hacker News API
        ↓
      landing
        ↓
arquivo NDJSON no Volume
        ↓
medallion_pipeline
        ↓
Bronze / Quarentena
        ↓
Silver
        ↓
Gold
```

As duas tasks devem finalizar com status:

```text
Succeeded
```

---

# 12. Validar a Landing

Após a task `landing`, acesse:

```text
Catalog Explorer
→ hackernews
→ hacker_news
→ Volumes
→ data
→ landing
```

Os arquivos devem seguir aproximadamente:

```text
landing/AAAA/MM/DD/arquivo.ndjson
```

Exemplo:

```text
landing/2026/09/29/hacker_news_183000.ndjson
```

Cada execução do Job gera um novo snapshot.

Os snapshots antigos não devem ser apagados.

---

# 13. Validar Bronze e Quarentena

Após o Pipeline executar, devem existir:

```text
hackernews.hacker_news.bronze_stories

hackernews.hacker_news.quarantine_stories
```

A `bronze_stories` contém registros aprovados pelas regras de qualidade.

A `quarantine_stories` contém registros rejeitados pelas regras de qualidade, permitindo identificar o motivo da rejeição.

---

# 14. Validar Silver

Deve existir:

```text
hackernews.hacker_news.silver_story_snapshots
```

Execute:

```sql
SELECT
    (SELECT COUNT(*)
     FROM hackernews.hacker_news.bronze_stories) AS bronze,

    (SELECT COUNT(*)
     FROM hackernews.hacker_news.silver_story_snapshots) AS silver;
```

Também valide possíveis duplicidades:

```sql
SELECT
    story_id,
    collected_at,
    COUNT(*) AS qtd
FROM hackernews.hacker_news.silver_story_snapshots
GROUP BY story_id, collected_at
HAVING COUNT(*) > 1;
```

O resultado esperado é:

```text
nenhuma linha
```

A granularidade da Silver é:

```text
uma notícia por snapshot
```

Sua chave lógica é:

```text
story_id + collected_at
```

Para verificar o histórico existente:

```sql
SELECT
    COUNT(DISTINCT collected_at) AS snapshots,
    COUNT(DISTINCT story_id) AS noticias,
    COUNT(*) AS linhas
FROM hackernews.hacker_news.silver_story_snapshots;
```

---

# 15. Validar Gold

Após uma execução bem-sucedida devem existir:

```text
hackernews.hacker_news.gold_story_timeline

hackernews.hacker_news.gold_story_summary

hackernews.hacker_news.gold_domain_stats

hackernews.hacker_news.gold_trend_index
```

Validação:

```sql
SELECT
    (SELECT COUNT(*)
     FROM hackernews.hacker_news.silver_story_snapshots)
        AS silver_linhas,

    (SELECT COUNT(*)
     FROM hackernews.hacker_news.gold_story_timeline)
        AS timeline_linhas,

    (SELECT COUNT(DISTINCT story_id)
     FROM hackernews.hacker_news.silver_story_snapshots)
        AS silver_noticias,

    (SELECT COUNT(*)
     FROM hackernews.hacker_news.gold_story_summary)
        AS summary_linhas;
```

O Índice de Tendência deve representar apenas o snapshot mais recente:

```sql
SELECT
    (SELECT COUNT(*)
     FROM hackernews.hacker_news.gold_trend_index)
        AS noticias_no_indice,

    (SELECT COUNT(*)
     FROM hackernews.hacker_news.silver_story_snapshots
     WHERE collected_at = (
         SELECT MAX(collected_at)
         FROM hackernews.hacker_news.silver_story_snapshots
     ))
        AS noticias_no_ultimo_snapshot;
```

---

# 16. Consultas de exploração da Gold

## Notícias em alta

```sql
SELECT
    trend_rank,
    trend_index,
    title,
    rank,
    score,
    comments
FROM hackernews.hacker_news.gold_trend_index
ORDER BY trend_rank;
```

## Evolução de uma notícia

```sql
SELECT
    collected_at,
    rank,
    score,
    comments,
    rank_change,
    score_delta
FROM hackernews.hacker_news.gold_story_timeline
WHERE story_id = '<story_id>'
ORDER BY collected_at;
```

## Notícias com maior permanência no Top N

```sql
SELECT
    title,
    hours_in_top_n,
    best_rank,
    peak_score
FROM hackernews.hacker_news.gold_story_summary
ORDER BY hours_in_top_n DESC;
```

## Domínios mais recorrentes

```sql
SELECT
    domain,
    stories_count,
    stories_reached_top_n,
    avg_peak_score
FROM hackernews.hacker_news.gold_domain_stats
ORDER BY stories_count DESC;
```

---

# 17. Criar as views do relatório de qualidade

O Bundle cria a infraestrutura principal, mas as views definidas em:

```text
notebooks/03_quality_report.sql
```

devem ser criadas após a primeira execução bem-sucedida do Pipeline.

Execute esse arquivo uma única vez.

Ele deve criar:

```text
hackernews.hacker_news.pipeline_runs

hackernews.hacker_news.quality_expectations
```

As views consultam diretamente:

```text
hackernews.hacker_news.pipeline_event_log
```

Portanto, não é necessário executar novamente o SQL após cada Pipeline.

O comportamento é:

```text
Pipeline executa
↓
Event Log recebe novos eventos
↓
Views refletem automaticamente os novos dados
```

---

# 18. Validar monitoramento e qualidade

## Histórico de execuções

```sql
SELECT *
FROM hackernews.hacker_news.pipeline_runs
ORDER BY started_at DESC;
```

A view permite acompanhar informações como:

- início da execução;
- fim da execução;
- status;
- registros enviados para Bronze;
- registros enviados para Quarentena;
- total processado;
- percentual de registros válidos.

## Regras de qualidade

```sql
SELECT *
FROM hackernews.hacker_news.quality_expectations
ORDER BY processed_at DESC, expectation;
```

Essa view permite acompanhar quantos registros:

- passaram em cada regra;
- falharam;
- foram processados;
- atingiram determinado percentual de sucesso.

---

# 19. Resultado esperado da configuração automática

Ao final da Parte 1, a arquitetura deve estar aproximadamente assim:

```text
GitHub
  │
  │ main
  ▼
Databricks
  │
  ├── Catalog: hackernews
  │     └── Schema: hacker_news
  │           └── Volume: data
  │
  ├── SQL Warehouse
  │     └── Hacker News SQL Warehouse
  │
  ├── Job: Hacker News Pipeline
  │     │
  │     ├── landing
  │     │
  │     └── medallion_pipeline
  │
  ├── Pipeline: Hacker News - Medallion Pipeline
  │     │
  │     ├── Landing → Bronze
  │     ├── Bronze → Silver
  │     └── Silver → Gold
  │
  └── App: hackernews
        │
        └── SQL Warehouse
```

Se todos esses componentes existirem e o Job executar corretamente, **não é necessário realizar a Parte 2**.

---

# PARTE 2 — CONFIGURAÇÃO MANUAL

Esta parte deve ser utilizada caso:

- o `databricks.yml` não possa ser executado;
- o Bundle apresente erro;
- o workspace não suporte algum recurso utilizado pelo Bundle;
- algum recurso não tenha sido criado corretamente.

> Se o Bundle criou apenas parte dos recursos, não crie objetos duplicados. Primeiro verifique o que já existe e configure manualmente somente os recursos ausentes.

---

# 20. Conectar o repositório manualmente

Acesse:

```text
Workspace
→ Create
→ Git folder
```

Utilize:

```text
Repository:
https://github.com/Andre2217/ProjetoFinalEngDados

Branch:
main
```

Confirme que todos os notebooks estão disponíveis.

---

# 21. Criar Unity Catalog manualmente

Abra:

```text
notebooks/00_setup.sql
```

Execute:

```sql
CREATE CATALOG IF NOT EXISTS hackernews;

CREATE SCHEMA IF NOT EXISTS hackernews.hacker_news;

CREATE VOLUME IF NOT EXISTS hackernews.hacker_news.data;
```

Caso seja necessário reproduzir também as permissões utilizadas pelo Bundle:

```sql
GRANT ALL PRIVILEGES
ON CATALOG hackernews
TO `account users`;

GRANT ALL PRIVILEGES
ON SCHEMA hackernews.hacker_news
TO `account users`;

GRANT ALL PRIVILEGES
ON VOLUME hackernews.hacker_news.data
TO `account users`;
```

Depois acesse:

```text
Catalog Explorer
→ hackernews
→ hacker_news
→ Volumes
→ data
```

---

# 22. Criar SQL Warehouse manualmente

Acesse:

```text
SQL
→ SQL Warehouses
→ Create SQL warehouse
```

Utilize:

```text
Name:
Hacker News SQL Warehouse
```

Configuração recomendada:

```text
Compute: Serverless
Size: 2X-Small
Min clusters: 1
Max clusters: 1
Auto Stop: 10 minutos
```

Se essas opções não estiverem disponíveis no workspace, utilize um SQL Warehouse Serverless já existente.

Em ambientes como Free Edition, pode existir:

```text
Serverless Starter Warehouse
```

Esse Warehouse também pode ser utilizado.

---

# 23. Testar a Landing manualmente

Abra:

```text
notebooks/01_landing.py
```

Execute o notebook.

O fluxo esperado é:

```text
Hacker News API
↓
Top Stories
↓
Detalhes das notícias
↓
NDJSON
↓
Unity Catalog Volume
```

Confirme os arquivos em:

```text
/Volumes/hackernews/hacker_news/data/landing
```

Estrutura esperada:

```text
landing/AAAA/MM/DD/arquivo.ndjson
```

---

# 24. Criar o ETL Pipeline manualmente

Acesse:

```text
Jobs & Pipelines
→ New
→ ETL Pipeline
```

Configure:

```text
Name:
Hacker News - Medallion Pipeline
```

Destino padrão:

```text
Catalog:
hackernews

Schema:
hacker_news
```

Utilize compute:

```text
Serverless
```

quando disponível.

---

# 25. Adicionar os códigos do Pipeline

Inclua os três arquivos no mesmo ETL Pipeline:

```text
notebooks/02_landing_to_bronze.py

notebooks/04_bronze_to_silver.py

notebooks/05_silver_to_gold.py
```

Não devem ser criados três Pipelines diferentes.

Todos fazem parte de:

```text
Hacker News - Medallion Pipeline
```

Isso permite que o Lakeflow identifique as dependências entre:

```text
Bronze
↓
Silver
↓
Gold
```

Se o Databricks criar arquivos de exemplo automaticamente, remova esses arquivos das fontes do Pipeline.

---

# 26. Configurar o Event Log manualmente

Abra as configurações do Pipeline.

Configure a publicação do Event Log em:

```text
Catalog:
hackernews

Schema:
hacker_news

Name:
pipeline_event_log
```

O resultado será:

```text
hackernews.hacker_news.pipeline_event_log
```

---

# 27. Validar o Pipeline manualmente

Antes da primeira execução, utilize:

```text
Dry run
```

O Dry Run verifica a definição do Pipeline sem realizar a atualização completa dos datasets.

Se não houver erros:

```text
Run pipeline
```

Após a execução devem existir:

```text
bronze_stories

quarantine_stories

silver_story_snapshots

gold_story_timeline

gold_story_summary

gold_domain_stats

gold_trend_index

pipeline_event_log
```

dentro de:

```text
hackernews.hacker_news
```

---

# 28. Criar as views de qualidade manualmente

Após o primeiro Pipeline bem-sucedido, execute:

```text
notebooks/03_quality_report.sql
```

Confirme a criação de:

```text
hackernews.hacker_news.pipeline_runs

hackernews.hacker_news.quality_expectations
```

---

# 29. Criar o Lakeflow Job manualmente

Acesse:

```text
Jobs & Pipelines
→ New
→ Job
```

Nome:

```text
Hacker News Pipeline
```

---

## 29.1. Configurar Git no Job

Configure o Job para utilizar:

```text
Git provider:
GitHub

Repository:
https://github.com/Andre2217/ProjetoFinalEngDados

Branch:
main
```

---

## 29.2. Criar Task 1 — Landing

Configure:

```text
Task name:
landing

Type:
Notebook

Source:
Git provider

Path:
notebooks/01_landing

Compute:
Serverless
```

Essa task será responsável por gerar um novo snapshot.

---

## 29.3. Criar Task 2 — Medallion Pipeline

Configure:

```text
Task name:
medallion_pipeline

Type:
Pipeline

Pipeline:
Hacker News - Medallion Pipeline
```

Em:

```text
Depends on
```

selecione:

```text
landing
```

Em:

```text
Run if dependencies
```

utilize:

```text
All succeeded
```

O fluxo final deve aparecer como:

```text
landing
   │
   ▼
medallion_pipeline
```

---

# 30. Configurar retries

Para aumentar a tolerância a falhas temporárias, recomenda-se configurar nas tasks:

```text
Maximum retries:
2

Retry interval:
2 minutos
```

O objetivo é permitir nova tentativa em casos como:

- falha temporária da API;
- indisponibilidade momentânea do serviço;
- erro transitório do Databricks.

---

# 31. Configurar o agendamento manualmente

Dentro de:

```text
Hacker News Pipeline
```

acesse:

```text
Schedules & Triggers
→ Add trigger
```

Selecione:

```text
Scheduled
```

Configure uma execução:

```text
a cada 30 minutos
```

Utilize timezone:

```text
America/Fortaleza
```

Ative o agendamento.

---

# 32. Testar o Job manualmente

Antes de depender do Schedule, clique em:

```text
Run now
```

O fluxo esperado é:

```text
landing
↓
novo NDJSON
↓
medallion_pipeline
↓
Bronze
↓
Silver
↓
Gold
```

As duas tasks devem terminar como:

```text
Succeeded
```

Depois valide as tabelas utilizando os procedimentos das seções 12 a 18 deste documento.

---

# 33. Criar o Databricks App manualmente

Acesse:

```text
Apps
→ Create app
→ Create custom app
```

Nome:

```text
hackernews
```

Configure o Git:

```text
Repository:
https://github.com/Andre2217/ProjetoFinalEngDados

Provider:
GitHub

Reference:
main
```

O repositório precisa possuir os arquivos necessários para execução da aplicação Streamlit.

---

# 34. Associar o SQL Warehouse ao App

Dentro das configurações do App:

```text
App resources
→ Add resource
→ SQL Warehouse
```

Selecione:

```text
Hacker News SQL Warehouse
```

Permissão:

```text
Can use
```

Utilize uma chave de recurso compatível com a configuração da aplicação, por exemplo:

```text
sql_warehouse
```

O App utiliza esse Warehouse para consultar as tabelas Gold.

---

# 35. Permissões do App no Unity Catalog

O Databricks App executa utilizando uma identidade própria.

Essa identidade precisa conseguir consultar:

```text
hackernews.hacker_news
```

No Catalog Explorer, abra as permissões do Catalog/Schema e conceda à identidade do App pelo menos:

```text
USE CATALOG
USE SCHEMA
SELECT
```

sobre os dados necessários ao dashboard.

Para este projeto, o principal consumo do App ocorre nas tabelas Gold.

---

# 36. Implantar o App

Abra:

```text
Apps
→ hackernews
```

Clique em:

```text
Deploy
```

Selecione a origem:

```text
Git
```

e a referência:

```text
main
```

Após o deploy, aguarde o status:

```text
Running
```

Abra o endereço disponibilizado pelo Databricks e confirme que o dashboard consegue consultar os dados.

Caso a aplicação apresente erro:

```text
Apps
→ hackernews
→ Logs
```

utilize os logs para identificar o problema.

---

# 37. Processamento incremental

A Landing mantém todos os snapshots gerados.

Exemplo:

```text
landing/
├── arquivo_1000.ndjson
├── arquivo_1030.ndjson
├── arquivo_1100.ndjson
└── arquivo_1130.ndjson
```

Na primeira execução do Pipeline:

```text
arquivo_1000 → processado
arquivo_1030 → processado
arquivo_1100 → processado
```

Posteriormente:

```text
arquivo_1130.ndjson
```

é criado.

Na execução seguinte:

```text
arquivo_1000 → já processado
arquivo_1030 → já processado
arquivo_1100 → já processado
arquivo_1130 → processado
```

Esse comportamento é controlado pelo Auto Loader e pelo estado do Lakeflow Pipeline.

Não é necessário apagar nem mover snapshots antigos.

---

# 38. Atualização do código pelo Git

Antes de começar a trabalhar:

```bash
git pull
```

Depois das alterações:

```bash
git status
git add .
git commit -m "descricao da alteracao"
git push
```

O código e a definição da infraestrutura devem permanecer versionados no GitHub.

O `databricks.yml` permite que a configuração dos principais recursos Databricks também seja mantida como código.

---

# 39. Procedimento após alterações no projeto

Quando apenas código Python ou SQL for alterado:

```text
git push
↓
atualizar o Git Folder
↓
executar novamente o Job/Pipeline
```

Quando o arquivo:

```text
databricks.yml
```

for alterado, execute novamente:

```text
Deployments
→ Deploy
```

ou:

```bash
databricks bundle validate -t default
databricks bundle deploy -t default
```

O Bundle aplicará as alterações necessárias aos recursos gerenciados.

---

# 40. O que fazer caso o Bundle falhe parcialmente

Se o deploy do `databricks.yml` apresentar erro:

1. leia o erro apresentado em `Project output`;
2. identifique qual recurso falhou;
3. verifique quais recursos já foram criados;
4. não recrie objetos que já existam;
5. utilize a Parte 2 somente para os recursos ausentes ou incorretos.

Exemplo:

```text
Catalog       → criado
Schema        → criado
Volume        → criado
Warehouse     → criado
Pipeline      → criado
Job           → criado
App           → erro
```

Nesse caso, não é necessário executar toda a configuração manual.

Utilize apenas:

```text
Parte 2
→ Criar/configurar Databricks App manualmente
```

O mesmo princípio vale para qualquer outro recurso.

> Evite utilizar `databricks bundle destroy` em ambientes que já possuam dados importantes sem verificar exatamente quais recursos serão removidos.

---

# 41. Checklist de validação final

Antes de considerar o ambiente reproduzido corretamente, confirme:

```text
[ ] Repositório Git conectado

[ ] Catalog hackernews criado

[ ] Schema hacker_news criado

[ ] Volume data criado

[ ] Landing gravando arquivos NDJSON

[ ] SQL Warehouse disponível

[ ] Hacker News - Medallion Pipeline criado

[ ] 02_landing_to_bronze.py incluído

[ ] 04_bronze_to_silver.py incluído

[ ] 05_silver_to_gold.py incluído

[ ] pipeline_event_log criado

[ ] bronze_stories criada

[ ] quarantine_stories criada

[ ] silver_story_snapshots criada

[ ] gold_story_timeline criada

[ ] gold_story_summary criada

[ ] gold_domain_stats criada

[ ] gold_trend_index criada

[ ] pipeline_runs criada

[ ] quality_expectations criada

[ ] Hacker News Pipeline criado

[ ] Task landing criada

[ ] Task medallion_pipeline criada

[ ] Dependência landing → medallion_pipeline configurada

[ ] Schedule de 30 minutos configurado

[ ] Job executado com sucesso

[ ] Databricks App hackernews criado

[ ] SQL Warehouse associado ao App

[ ] App consegue acessar Unity Catalog

[ ] Dashboard abre e apresenta os dados
```

---

# 42. Fluxo final do projeto

A arquitetura completa é:

```text
                    GitHub
                       │
                       ▼
                databricks.yml
                       │
        ┌──────────────┼───────────────┐
        │              │               │
        ▼              ▼               ▼
 Unity Catalog      Lakeflow         Databricks
                     Job                App
        │              │               │
        │              ▼               │
        │           landing             │
        │              │               │
        │              ▼               │
        │       Medallion Pipeline      │
        │              │               │
        │              ▼               │
        │           Bronze              │
        │              │               │
        │              ▼               │
        │           Silver              │
        │              │               │
        │              ▼               │
        │            Gold ──────────────┤
        │                              │
        │                       SQL Warehouse
        │                              │
        └──────────────────────────────┘
                                       │
                                       ▼
                                   Dashboard
```

O fluxo operacional normal é:

```text
Schedule a cada 30 minutos
↓
Hacker News Pipeline
↓
landing
↓
novo snapshot NDJSON
↓
medallion_pipeline
↓
Bronze
↓
Silver
↓
Gold
↓
Dashboard atualizado
```

---

# Resumo para um novo ambiente

## Método recomendado

```text
1. Conectar o GitHub ao Databricks
2. Abrir databricks.yml
3. Abrir Deployments
4. Selecionar target default
5. Clicar em Deploy
6. Validar Catalog / Schema / Volume
7. Validar SQL Warehouse
8. Validar Pipeline
9. Validar Job
10. Validar App
11. Executar Hacker News Pipeline manualmente uma vez
12. Executar 03_quality_report.sql uma única vez
13. Validar Bronze, Silver e Gold
14. Abrir o dashboard
```

## Caso o Bundle não funcione

```text
1. Conectar o GitHub
2. Executar 00_setup.sql
3. Criar SQL Warehouse
4. Testar 01_landing.py
5. Criar Hacker News - Medallion Pipeline
6. Adicionar 02_landing_to_bronze.py
7. Adicionar 04_bronze_to_silver.py
8. Adicionar 05_silver_to_gold.py
9. Configurar pipeline_event_log
10. Executar Dry Run
11. Executar Pipeline
12. Executar 03_quality_report.sql
13. Criar Hacker News Pipeline
14. Criar task landing
15. Criar task medallion_pipeline
16. Configurar dependência entre as tasks
17. Configurar Schedule de 30 minutos
18. Criar Databricks App hackernews
19. Associar SQL Warehouse
20. Configurar permissões
21. Deploy do App
22. Executar o Job
23. Validar todo o fluxo
```

Após a configuração inicial, a operação normal acontece automaticamente através do:

```text
Hacker News Pipeline
```

executado a cada 30 minutos.