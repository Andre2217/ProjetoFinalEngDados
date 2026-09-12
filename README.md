# Pipeline de Monitoramento e Detecção de Tendências Tecnológicas no Hacker News

Projeto desenvolvido para a disciplina de **Projetos da Pós-Graduação em Engenharia de Dados da UNIFOR**.

## Objetivo

Construir uma pipeline de Engenharia de Dados capaz de coletar periodicamente as principais notícias do Hacker News, armazenar snapshots históricos e transformar esses dados em indicadores que permitam identificar tendências tecnológicas.

A proposta não é apenas exibir as notícias atuais, mas acompanhar sua evolução ao longo do tempo.

Entre as análises previstas estão:

- evolução do score;
- evolução da quantidade de comentários;
- evolução da posição no ranking;
- tempo de permanência no Top N;
- notícias com maior crescimento;
- fontes/domínios mais recorrentes;
- temas com maior engajamento;
- tendências emergentes;
- criação de um Índice de Tendência.

---

## Fonte de dados

Será utilizada inicialmente apenas a API pública oficial do Hacker News:

- `/topstories.json`
- `/item/{id}.json`

A API é pública e não exige chave de acesso.

---

## Arquitetura

A arquitetura prevista é:

Hacker News API  
↓  
Databricks  
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

### Landing

Responsável por armazenar os dados praticamente no formato original recebido da API.

Os dados são salvos em formato **NDJSON**, contendo uma notícia por linha.

Exemplo de caminho:

`/Volumes/hackernews/hacker_news/data/landing/`

Os arquivos são organizados por data:

`landing/2026/09/11/hacker_news_193000.ndjson`

---

### Bronze

A camada Bronze receberá os dados da Landing após validações de qualidade.

Será utilizada a biblioteca **Great Expectations** para validações como:

- campos obrigatórios;
- tipos esperados;
- valores nulos;
- registros inválidos;
- consistência básica dos dados.

---

### Silver

A camada Silver será responsável pela estruturação e consolidação histórica dos snapshots.

A ideia é manter uma tabela histórica com dados como:

- story_id;
- title;
- author;
- url;
- domain;
- score;
- comments;
- rank;
- published_at;
- collected_at.

Uma mesma notícia poderá aparecer diversas vezes, permitindo acompanhar sua evolução ao longo do tempo.

---

### Gold

A camada Gold será responsável pelas métricas analíticas e regras de negócio.

Exemplos previstos:

- crescimento de score;
- crescimento de comentários;
- variação de ranking;
- tempo no Top 10;
- notícias emergentes;
- domínios mais recorrentes;
- tendências por período;
- Índice de Tendência.

---

## Tecnologias

### Databricks

Plataforma principal do projeto.

Será utilizada para:

- desenvolvimento dos notebooks;
- processamento dos dados;
- armazenamento;
- uso de Spark;
- criação das camadas Bronze, Silver e Gold;
- execução e orquestração futura da pipeline.

### Apache Spark

Utilizado dentro do Databricks para processamento e transformação dos dados.

### Delta Lake

Previsto para armazenamento das camadas estruturadas do projeto, principalmente Bronze, Silver e Gold.

### Unity Catalog

Utilizado para organização dos dados e criação de Volumes e tabelas.

Estrutura atual:

- Catalog: `hackernews`
- Schema: `hacker_news`
- Volume: `data`

Caminho da Landing:

`/Volumes/hackernews/hacker_news/data/landing`

### Great Expectations

Será utilizado para validação e qualidade dos dados.

### Requests

Utilizado para realizar as requisições HTTP à API do Hacker News.

### Streamlit

Será utilizado como camada de consumo final, apresentando dashboards e indicadores da pipeline.

### pytest

Utilizado para testes automatizados.

### Git + GitHub

Utilizados para versionamento, colaboração entre os integrantes e entrega do código.

---

## Estrutura atual do projeto

ProjetoFinalEngDados/

- notebooks/
  - 00_setup.sql
  - 01_landing.py
- docs/
  - architecture.md
- tests/
- requirements.txt
- .gitignore
- README.md

A estrutura poderá crescer conforme as próximas etapas forem implementadas.

---

## Configuração inicial

### 1. Clonar o repositório

```bash
git clone https://github.com/Andre2217/ProjetoFinalEngDados.git
```
### 2. Abrir o projeto no Databricks

O repositório pode ser conectado ao Databricks através de uma Git Folder.

### 3. Criar a estrutura no Unity Catalog

Executar o arquivo:

`notebooks/00_setup.sql`

Conteúdo:
```sql
CREATE SCHEMA IF NOT EXISTS hackernews.hacker_news;

CREATE VOLUME IF NOT EXISTS hackernews.hacker_news.data;
```
Isso cria a estrutura necessária para armazenamento dos arquivos da Landing.

### 4. Executar a Landing

Executar:

`notebooks/01_landing.py`

O notebook realiza o fluxo:

Hacker News API
↓
requisição HTTP
↓
coleta das Top Stories
↓
coleta dos detalhes das notícias
↓
arquivo NDJSON
↓
Unity Catalog Volume

Os arquivos são armazenados em:

`/Volumes/hackernews/hacker_news/data/landing`

### Dependências

Arquivo `requirements.txt:`
```txt
requests==2.32.5
great-expectations==1.9.3
pytest==8.4.2
streamlit==1.49.1
```
O Databricks já fornece Spark/PySpark no ambiente, portanto essas bibliotecas não precisam ser adicionadas manualmente ao `requirements.txt:`

### Status atual

Atualmente o projeto possui:

- definição da arquitetura;
- integração com GitHub;
- ambiente no Databricks;
- Catalog, Schema e Volume configurados;
- ingestão da API do Hacker News funcionando;
- Landing em NDJSON funcionando;
- organização dos snapshots por data.

**Fluxo atual:**

Hacker News API -> Databricks -> Landing NDJSON

### Resultado esperado

Ao final, o projeto deverá permitir acompanhar a evolução das principais notícias do Hacker News e identificar quais conteúdos e tecnologias estão ganhando relevância ao longo do tempo.

A solução será apresentada como uma:

Pipeline de Engenharia de Dados para Monitoramento e Detecção de Tendências Tecnológicas a partir do Hacker News.