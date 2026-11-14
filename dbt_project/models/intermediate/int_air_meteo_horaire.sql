select
    a.city_id,
    a.observed_at,
    a.pm2_5,
    a.pm10,
    a.no2,
    a.so2,
    a.o3,
    m.temperature_c,
    m.humidity_pct,
    m.precipitation_mm,
    m.wind_speed_kmh
from {{ ref('stg_air') }} a
left join {{ ref('stg_meteo') }} m
    on a.city_id = m.city_id
   and a.observed_at = m.observed_at
