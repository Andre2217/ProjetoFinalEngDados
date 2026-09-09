# Arquitetura atual

## Fluxo

Hacker News API → Requests → Bronze NDJSON → Pandera → Silver DuckDB

Registros que não atendem ao contrato da Silver são enviados para `data/quarantine`.

O Prefect executa as etapas em sequência e aplica retry na coleta da API.

## Bronze

Granularidade: uma linha por notícia observada em um snapshot.

A Bronze mantém os metadados da coleta e o payload original retornado pelo Hacker News.

## Silver

Granularidade: uma notícia por snapshot.

Campos atuais:

- snapshot_id
- story_id
- collected_at
- list_type
- rank
- title
- author
- url
- domain
- score
- comments_count
- published_at
- item_type
- is_deleted
- is_dead

A Gold será definida e implementada em uma etapa posterior.
