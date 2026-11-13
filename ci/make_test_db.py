import duckdb, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else "data/airquality.duckdb"
os.makedirs(os.path.dirname(path), exist_ok=True)
con = duckdb.connect(path)
con.execute("create schema if not exists raw")

con.execute("""create or replace table raw.dim_ville_seed (
    city_id varchar, city_name varchar, latitude double,
    longitude double, zone_type varchar)""")
con.execute("""insert into raw.dim_ville_seed values
    ('gabes','Gab\u00e8s',33.88,10.10,'industrielle'),
    ('tunis','Tunis',36.80,10.18,'urbaine'),
    ('sfax','Sfax',34.74,10.76,'industrielle'),
    ('sousse','Sousse',35.83,10.64,'c\u00f4ti\u00e8re'),
    ('bizerte','Bizerte',37.27,9.87,'c\u00f4ti\u00e8re'),
    ('gafsa','Gafsa',34.43,8.78,'industrielle')""")

con.execute("""create or replace table raw.raw_air (
    city_id varchar, observed_at timestamp, pm2_5 double, pm10 double,
    nitrogen_dioxide double, sulphur_dioxide double, ozone double,
    ingested_at timestamp, source varchar,
    primary key (city_id, observed_at))""")
con.execute("""create or replace table raw.raw_meteo (
    city_id varchar, observed_at timestamp, temperature_2m double,
    relative_humidity_2m double, precipitation double,
    wind_speed_10m double, wind_direction_10m double,
    ingested_at timestamp, source varchar,
    primary key (city_id, observed_at))""")

for city in ["gabes", "tunis", "sfax", "sousse", "bizerte", "gafsa"]:
    for h in range(6):
        con.execute(f"""insert into raw.raw_air values
            ('{city}', timestamp '2025-01-01 0{h}:00:00', {10+h*5}, {20+h*8},
             15, 5, 60, now(), 'open-meteo-air')""")
        con.execute(f"""insert into raw.raw_meteo values
            ('{city}', timestamp '2025-01-01 0{h}:00:00', {12+h}, 55,
             {0 if h < 3 else 1.2}, {10+h}, 180, now(), 'open-meteo-forecast')""")
con.close()
print("OK:", path)
