with source as (
    select * from {{ source('raw', 'raw_meteo') }}
),

dedup as (
    select *
    from source
    qualify row_number() over (
        partition by city_id, observed_at
        order by ingested_at desc
    ) = 1
)

select
    city_id,
    observed_at,
    temperature_2m       as temperature_c,
    relative_humidity_2m as humidity_pct,
    precipitation        as precipitation_mm,
    wind_speed_10m       as wind_speed_kmh,
    wind_direction_10m   as wind_direction_deg,
    ingested_at
from dedup
