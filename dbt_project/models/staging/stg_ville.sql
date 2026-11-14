select
    city_id,
    city_name,
    latitude,
    longitude,
    zone_type
from {{ source('raw', 'dim_ville_seed') }}
