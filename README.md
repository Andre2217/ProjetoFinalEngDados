# Pipeline de Monitoramento e Detecção de Tendências Tecnológicas no Hacker News

Projeto desenvolvido para a disciplina de **Projetos da Pós-Graduação em Engenharia de Dados da UNIFOR**.

## Objetivo

Construir uma pipeline de Engenharia de Dados capaz de coletar periodicamente as principais notícias do Hacker News, armazenar snapshots históricos e transformar esse fluxo de dados em indicadores que permitam identificar tendências tecnológicas.

A proposta não é apenas apresentar as notícias atuais, mas acompanhar sua evolução ao longo do tempo.

Entre as análises previstas estão:

- evolução do score;
- evolução da quantidade de comentários;
- evolução da posição no ranking;
- tempo de permanência no Top N;
- notícias com maior crescimento;
- fontes e domínios mais recorrentes;
- temas com maior engajamento;
- tendências emergentes;
- criação de um Índice de Tendência.

---

## Fonte de dados

A fonte utilizada é a API pública oficial do Hacker News, disponibilizada através do Firebase.

Principais endpoints utilizados:

- `/topstories.json`
- `/item/{id}.json`

A API é pública e não exige API Key.

---

## Arquitetura

A arquitetura geral planejada é:

Hacker News API  
↓  
Landing  
↓  
Bronze  
↓  
Silver  
↓  
Gold  
↓  
Streamlit

O processamento, armazenamento estruturado e orquestração são realizados dentro da plataforma Databricks.

### Fluxo atual implementado

Hacker News API  
↓  
Databricks  
↓  
Landing em NDJSON  
↓  
Auto Loader  
↓  
Padronização com Spark  
↓  
Expectations do Lakeflow  
↓  
Bronze / Quarentena  
↓  
Event Log de qualidade

---

## Camadas

### Landing

A Landing preserva os dados provenientes da API o mais próximo possível do formato original.

Cada execução consulta as principais notícias do Hacker News e gera um novo snapshot em formato NDJSON.

Cada linha representa uma notícia observada naquele momento.

Os arquivos são armazenados no Unity Catalog Volume:

`/Volumes/hackernews/hacker_news/data/landing`

A organização utiliza partições de diretório por data:

`landing/AAAA/MM/DD/hacker_news_HHMMSS.ndjson`

Exemplo:

`landing/2026/09/12/hacker_news_103000.ndjson`

Os snapshots da Landing não são sobrescritos, permitindo construir o histórico necessário para as análises futuras.

---

### Bronze

A Bronze contém os registros da Landing que passaram pelas regras de qualidade.

A ingestão da Landing para a Bronze utiliza o Auto Loader do Databricks.

Isso permite processamento incremental:

- na primeira execução, são processados os arquivos existentes;
- nas execuções seguintes, somente arquivos ainda não processados são considerados.

Antes de serem persistidos, os dados passam por:

- tipagem;
- padronização;
- flatten do JSON;
- seleção das colunas necessárias;
- validações de qualidade.

Campos que não possuem utilidade analítica para o projeto, como `kids`, permanecem preservados na Landing, mas não são propagados para a Bronze.

A Bronze é persistida como tabela Delta:

`hackernews.hacker_news.bronze_stories`

Principais campos:

- record_key;
- collected_at;
- source;
- list_type;
- rank;
- story_id;
- title;
- author;
- url;
- domain;
- text;
- score;
- comments;
- published_at;
- item_type;
- source_file;
- source_file_modified_at;
- bronze_loaded_at.

---

### Quarentena

Registros que não atendem às regras de qualidade não são descartados silenciosamente.

Eles são direcionados para:

`hackernews.hacker_news.quarantine_stories`

A tabela preserva o registro problemático, sua origem e as regras de qualidade que foram violadas.

Isso permite investigar problemas sem interromper ou comprometer a camada Bronze.

---

### Silver

A camada Silver será responsável pela consolidação histórica dos snapshots.

A ideia é manter uma estrutura limpa e consistente em que uma mesma notícia possa aparecer em diferentes momentos de coleta.

Isso permitirá observar, por exemplo:

- score às 10:00;
- score às 10:30;
- score às 11:00;
- posição no ranking em cada coleta;
- número de comentários em cada coleta.

A implementação da Silver será realizada nas próximas etapas do projeto.

---

### Gold

A camada Gold será responsável pelas regras analíticas e indicadores finais.

Entre as métricas previstas estão:

- crescimento de score;
- crescimento de comentários;
- variação de ranking;
- tempo de permanência no Top 10;
- notícias com crescimento mais rápido;
- domínios mais recorrentes;
- tendências por período;
- Índice de Tendência.

A implementação da Gold será realizada após a consolidação da Silver.

---

## Qualidade de dados

A qualidade é implementada através das **Expectations nativas do Lakeflow Declarative Pipelines**.

Entre as regras aplicadas atualmente estão:

- `story_id` obrigatório e positivo;
- `story_id` compatível com o ID retornado pelo item;
- data de coleta válida;
- ranking dentro da faixa esperada;
- título obrigatório;
- score não negativo;
- quantidade de comentários não negativa;
- data de publicação válida;
- origem dos dados esperada;
- tipo de lista esperado;
- item do tipo `story`;
- registros não deletados ou mortos;
- compatibilidade com o schema definido;
- JSON válido.

Registros aprovados seguem para a Bronze.

Registros reprovados seguem para a Quarentena.

---

## Monitoramento e auditoria

O Lakeflow mantém automaticamente um Event Log das execuções do pipeline.

O log foi publicado no Unity Catalog como:

`hackernews.hacker_news.pipeline_event_log`

Ele registra informações como:

- horário das execuções;
- status;
- identificador da atualização;
- fluxos executados;
- quantidade de registros;
- resultados das Expectations;
- falhas e erros do pipeline.

Também são criadas views para facilitar a consulta dessas informações:

`hackernews.hacker_news.pipeline_runs`

`hackernews.hacker_news.quality_expectations`

Essas views permitem acompanhar o histórico de execução e qualidade sem depender de arquivos de log externos.

---

## Orquestração

A orquestração geral utiliza Lakeflow Jobs.

O fluxo inicial é:

Task 1 — Landing  
`01_landing.py`

↓  

Task 2 — Landing para Bronze  
Lakeflow ETL Pipeline utilizando `02_landing_to_bronze.py`

Futuramente serão adicionadas tarefas para:

Silver  
↓  
Gold  
↓  
Atualização da camada de consumo

O Job será responsável por:

- ordenar as dependências;
- executar as tarefas;
- realizar retries;
- registrar falhas;
- permitir agendamento periódico.

---

## Tecnologias

### Databricks

Plataforma principal da solução.

Responsável pelo desenvolvimento, processamento, armazenamento, pipelines e orquestração.

### Apache Spark

Utilizado para leitura, tipagem, transformação, padronização e processamento distribuído dos dados.

### Delta Lake

Utilizado na persistência das tabelas estruturadas, fornecendo confiabilidade e suporte a operações incrementais.

### Unity Catalog

Utilizado para organizar:

- Catalog;
- Schema;
- Volumes;
- tabelas;
- views;
- Event Logs.

Estrutura atual:

Catalog:

`hackernews`

Schema:

`hacker_news`

Volume:

`data`

---

### Auto Loader

Responsável pela ingestão incremental dos arquivos NDJSON existentes na Landing.

Permite processar somente novos arquivos sem reler todo o histórico a cada execução.

---

### Lakeflow Declarative Pipelines

Responsável pelo fluxo Landing → Bronze.

Utiliza:

- Auto Loader;
- Spark;
- Expectations;
- tabelas Delta;
- Event Log;
- gerenciamento de estado incremental.

---

### Lakeflow Jobs

Responsável pela orquestração geral do projeto.

---

### Streamlit

Será utilizado como camada de consumo e visualização dos indicadores finais.

---

### pytest

Será utilizado para testes automatizados do código Python e das regras auxiliares do projeto.

---

### Git + GitHub

Utilizados para:

- versionamento;
- colaboração entre os integrantes;
- histórico de alterações;
- entrega do projeto.

Repositório:

`https://github.com/Andre2217/ProjetoFinalEngDados`

---

## Estrutura do projeto

ProjetoFinalEngDados/

notebooks/
- 00_setup.sql
- 01_landing.py
- 02_landing_to_bronze.py
- 03_quality_report.sql

docs/
- architecture.md

tests/

requirements.txt

.gitignore

README.md

RUNBOOK.md

---

## Dependências externas

O arquivo `requirements.txt` contém apenas bibliotecas adicionais necessárias ao projeto.

Atualmente:

```txt
requests==2.32.5
pytest==8.4.2
streamlit==1.49.1