"""Ingestion Open-Meteo (air + météo) -> DuckDB (schéma raw). Idempotent."""
import argparse
import csv
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests

DB_PATH = os.getenv("DUCKDB_PATH", "data/airquality.duckdb")
VILLES_CSV = os.getenv("VILLES_CSV", "data/seeds/villes.csv")

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
METEO_URL = "https://api.open-meteo.com/v1/forecast"

AIR_VARS = ["pm10", "pm2_5", "nitrogen_dioxide", "sulphur_dioxide", "ozone"]
METEO_VARS = ["temperature_2m", "relative_humidity_2m", "precipitation",
              "wind_speed_10m", "wind_direction_10m"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")


def init_db(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("""CREATE TABLE IF NOT EXISTS raw.dim_ville_seed (
        city_id VARCHAR PRIMARY KEY, city_name VARCHAR,
        latitude DOUBLE, longitude DOUBLE, zone_type VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS raw.raw_air (
        city_id VARCHAR, observed_at TIMESTAMP,
        pm2_5 DOUBLE, pm10 DOUBLE, nitrogen_dioxide DOUBLE,
        sulphur_dioxide DOUBLE, ozone DOUBLE,
        ingested_at TIMESTAMP, source VARCHAR,
        PRIMARY KEY (city_id, observed_at))""")
    con.execute("""CREATE TABLE IF NOT EXISTS raw.raw_meteo (
        city_id VARCHAR, observed_at TIMESTAMP,
        temperature_2m DOUBLE, relative_humidity_2m DOUBLE,
        precipitation DOUBLE, wind_speed_10m DOUBLE, wind_direction_10m DOUBLE,
        ingested_at TIMESTAMP, source VARCHAR,
        PRIMARY KEY (city_id, observed_at))""")


def load_villes(con):
    with open(VILLES_CSV, newline="", encoding="utf-8-sig") as f:
        villes = list(csv.DictReader(f))
    for v in villes:
        con.execute("INSERT OR REPLACE INTO raw.dim_ville_seed VALUES (?, ?, ?, ?, ?)",
                    [v["city_id"], v["city_name"], float(v["latitude"]),
                     float(v["longitude"]), v["zone_type"]])
    return villes


def fetch(url, ville, variables, past_days, retries=3):
    params = {"latitude": ville["latitude"], "longitude": ville["longitude"],
              "hourly": ",".join(variables), "past_days": past_days,
              "forecast_days": 1, "timezone": "UTC"}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()["hourly"]
        except requests.RequestException as e:
            log.warning("%s tentative %d/%d échouée : %s",
                        ville["city_id"], attempt, retries, e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"API KO pour {ville['city_id']} ({url})")


def to_rows(city_id, hourly, variables, source, now):
    rows = []
    for i, t in enumerate(hourly["time"]):
        values = [hourly[v][i] for v in variables]
        rows.append([city_id, datetime.fromisoformat(t), *values, now, source])
    return rows


def upsert(con, table, columns, rows):
    placeholders = ", ".join("?" * len(columns))
    con.executemany(
        f"INSERT OR REPLACE INTO raw.{table} ({', '.join(columns)}) VALUES ({placeholders})",
        rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--past-days", type=int, default=2)
    args = parser.parse_args()

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH)
    init_db(con)
    villes = load_villes(con)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    air_cols = ["city_id", "observed_at", *AIR_VARS, "ingested_at", "source"]
    meteo_cols = ["city_id", "observed_at", *METEO_VARS, "ingested_at", "source"]

    for v in villes:
        air = fetch(AIR_URL, v, AIR_VARS, args.past_days)
        upsert(con, "raw_air", air_cols,
               to_rows(v["city_id"], air, AIR_VARS, "open-meteo-air", now))
        meteo = fetch(METEO_URL, v, METEO_VARS, args.past_days)
        upsert(con, "raw_meteo", meteo_cols,
               to_rows(v["city_id"], meteo, METEO_VARS, "open-meteo-forecast", now))
        log.info("%s : %d lignes air, %d lignes météo",
                 v["city_id"], len(air["time"]), len(meteo["time"]))

    log.info("Total raw_air=%d, raw_meteo=%d",
             con.execute("SELECT COUNT(*) FROM raw.raw_air").fetchone()[0],
             con.execute("SELECT COUNT(*) FROM raw.raw_meteo").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()