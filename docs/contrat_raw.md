# Contrat de données : couche raw

Contrat entre l'ingestion (A) et dbt (B). Toute modification des colonnes ou des types passe par une PR relue par les deux.

- Base : DuckDB (`data/airquality.duckdb`), schéma `raw`
- Fréquence : horaire
- Fuseau : UTC
- Noms de colonnes identiques à ceux de l'API (le renommage se fait en staging avec dbt)

## raw.dim_ville_seed (CSV statique, 6 lignes)

Source : `data/seeds/villes.csv`

| colonne | type | note |
|---|---|---|
| city_id | VARCHAR | clé primaire (ex : `gabes`) |
| city_name | VARCHAR | |
| latitude | DOUBLE | |
| longitude | DOUBLE | |
| zone_type | VARCHAR | industrielle / urbaine / côtière |

## raw.raw_air (Open-Meteo Air Quality, horaire)

| colonne | type | note |
|---|---|---|
| city_id | VARCHAR | clé |
| observed_at | TIMESTAMP | clé (UTC) |
| pm2_5 | DOUBLE | µg/m³ |
| pm10 | DOUBLE | µg/m³ |
| nitrogen_dioxide | DOUBLE | µg/m³ |
| sulphur_dioxide | DOUBLE | µg/m³ |
| ozone | DOUBLE | µg/m³ |
| ingested_at | TIMESTAMP | date de chargement |
| source | VARCHAR | `open-meteo-air` |

## raw.raw_meteo (Open-Meteo Forecast, horaire)

| colonne | type | note |
|---|---|---|
| city_id | VARCHAR | clé |
| observed_at | TIMESTAMP | clé (UTC) |
| temperature_2m | DOUBLE | °C |
| relative_humidity_2m | DOUBLE | % |
| precipitation | DOUBLE | mm |
| wind_speed_10m | DOUBLE | km/h |
| wind_direction_10m | DOUBLE | degrés |
| ingested_at | TIMESTAMP | date de chargement |
| source | VARCHAR | `open-meteo-forecast` |

## Règles

1. Clé primaire `(city_id, observed_at)` sur `raw_air` et `raw_meteo`.
2. Insertion en `INSERT OR REPLACE` : relancer l'ingestion ne crée jamais de doublons (idempotence).
3. Les valeurs nulles sont acceptées en raw ; les tests dbt les détectent ensuite.
4. Les 6 villes : tunis, sfax, sousse, gabes, bizerte, gafsa.
5. Pas de transformation en raw : les données sont stockées telles que reçues de l'API.