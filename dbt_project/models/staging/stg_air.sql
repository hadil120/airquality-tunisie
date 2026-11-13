with source as (
    select * from {{ source('raw', 'raw_air') }}
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
    pm2_5,
    pm10,
    nitrogen_dioxide as no2,
    sulphur_dioxide  as so2,
    ozone            as o3,
    ingested_at
from dedup
