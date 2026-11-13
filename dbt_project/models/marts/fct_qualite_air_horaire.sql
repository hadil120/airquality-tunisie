select
    i.city_id,
    v.city_name,
    v.zone_type,
    i.observed_at,
    cast(i.observed_at as date) as observation_date,
    cast(extract(hour from i.observed_at) as integer) as hour_of_day,
    i.pm2_5,
    i.pm10,
    i.no2,
    i.so2,
    i.o3,
    i.temperature_c,
    i.humidity_pct,
    i.precipitation_mm,
    i.wind_speed_kmh,
    coalesce(i.pm2_5 > {{ var('who_pm25_threshold') }}, false) as is_pm25_above_who,
    coalesce(i.pm10  > {{ var('who_pm10_threshold') }}, false) as is_pm10_above_who,
    coalesce(i.precipitation_mm > 0, false) as is_raining
from {{ ref('int_air_meteo_horaire') }} i
left join {{ ref('dim_ville') }} v using (city_id)
