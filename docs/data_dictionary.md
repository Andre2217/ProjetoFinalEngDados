# Dicionário de dados inicial

## Bronze

Granularidade: uma notícia observada em um snapshot.

| Campo | Tipo | Descrição |
|---|---|---|
| snapshot_id | string | Identificador único da coleta |
| collected_at | timestamp UTC | Horário da coleta |
| source | string | Fonte do dado, atualmente `hacker_news` |
| list_type | string | Lista consultada, inicialmente `topstories` |
| rank | integer | Posição da notícia na lista durante a coleta |
| story_id | integer | Identificador do item no Hacker News |
| payload | JSON | Conteúdo original retornado pelo endpoint `/item/{id}.json` |

## Silver — `silver.story_snapshots`

Granularidade: uma notícia por snapshot.

| Campo | Tipo | Descrição |
|---|---|---|
| snapshot_id | varchar | Identificador do snapshot |
| story_id | bigint | Identificador da notícia |
| collected_at | timestamp | Horário UTC da coleta |
| list_type | varchar | Lista consultada |
| rank | integer | Posição no ranking |
| title | varchar | Título da notícia |
| author | varchar | Autor do item |
| url | varchar | URL externa da notícia, quando existir |
| domain | varchar | Domínio extraído da URL |
| score | bigint | Score observado no snapshot |
| comments_count | bigint | Quantidade de comentários observada |
| published_at | timestamp | Data/hora UTC de publicação |
| item_type | varchar | Tipo do item retornado pela API |
| is_deleted | boolean | Indica item marcado como deletado |
| is_dead | boolean | Indica item marcado como dead |

Chave lógica/primária: `snapshot_id + story_id + list_type`.
