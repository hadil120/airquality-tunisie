import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = os.getenv(
    "DUCKDB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "airquality.duckdb"),
)

st.set_page_config(page_title="Qualité de l'air - Tunisie", layout="wide")


def query(sql: str) -> pd.DataFrame:
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


@st.cache_data(ttl=300)
def load_fact() -> pd.DataFrame:
    return query("select * from main.fct_qualite_air_horaire")


@st.cache_data(ttl=300)
def load_health() -> dict:
    air = query(
        "select count(*) as n, max(ingested_at) as last_ingest, "
        "max(observed_at) as last_obs from raw.raw_air"
    ).iloc[0]
    meteo = query(
        "select count(*) as n, max(ingested_at) as last_ingest "
        "from raw.raw_meteo"
    ).iloc[0]
    return {"air": air, "meteo": meteo}


st.title("Qualité de l'air et météo en Tunisie")
st.caption("Source : Open-Meteo (Air Quality + Forecast) | Transformations : dbt | Base : DuckDB")

try:
    df = load_fact()
except Exception as e:
    st.error(
        "Impossible de lire `main.fct_qualite_air_horaire`. "
        "Lance d'abord `python ingestion\\ingest.py` puis `dbt build`."
    )
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("La table est vide. Lance l'ingestion puis dbt build.")
    st.stop()

# ---------- Filtres ----------
villes = sorted(df["city_name"].dropna().unique())
choix = st.sidebar.multiselect("Villes", villes, default=villes)
d = df[df["city_name"].isin(choix)]
if d.empty:
    st.info("Sélectionne au moins une ville.")
    st.stop()

tab1, tab2 = st.tabs(["Questions métier", "Santé des données"])

# ---------- Questions métier ----------
with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes horaires", f"{len(d):,}")
    c2.metric("PM2.5 moyen (µg/m³)", f"{d['pm2_5'].mean():.1f}")
    c3.metric("% heures PM2.5 > seuil OMS", f"{100 * d['is_pm25_above_who'].mean():.1f}%")

    st.subheader("Q1. Quelle ville dépasse le plus souvent les seuils OMS ?")
    q1 = (
        d.groupby("city_name")
        .agg(
            pct_pm25=("is_pm25_above_who", lambda s: 100 * s.mean()),
            pct_pm10=("is_pm10_above_who", lambda s: 100 * s.mean()),
        )
        .sort_values("pct_pm25", ascending=False)
        .round(1)
    )
    st.bar_chart(q1)
    st.dataframe(q1.rename(columns={"pct_pm25": "% heures PM2.5 > 15", "pct_pm10": "% heures PM10 > 45"}))
    st.caption(
        "Seuils OMS 2021 : PM2.5 = 15 µg/m³, PM10 = 45 µg/m³ (moyennes sur 24 h). "
        "Nos données sont horaires : comparaison approximative."
    )

    st.subheader("Q2. Le vent, la chaleur ou la pluie influencent-ils la pollution ?")
    col_a, col_b = st.columns(2)
    with col_a:
        pluie = (
            d.assign(pluie=d["is_raining"].map({True: "Il pleut", False: "Sec"}))
            .groupby("pluie")["pm2_5"]
            .mean()
            .round(1)
        )
        st.write("PM2.5 moyen selon la pluie")
        st.bar_chart(pluie)
    with col_b:
        corr = pd.DataFrame(
            {
                "Corrélation avec PM2.5": [
                    d["pm2_5"].corr(d["wind_speed_kmh"]),
                    d["pm2_5"].corr(d["temperature_c"]),
                    d["pm2_5"].corr(d["humidity_pct"]),
                ]
            },
            index=["Vent", "Température", "Humidité"],
        ).round(2)
        st.write("Corrélations")
        st.dataframe(corr)
    st.caption("Une corrélation n'est pas une causalité.")

    st.subheader("Q3. À quelle heure la pollution atteint-elle son pic, par ville ?")
    q3 = d.pivot_table(index="hour_of_day", columns="city_name", values="pm2_5", aggfunc="mean").round(1)
    st.line_chart(q3)
    pics = q3.idxmax().rename("Heure du pic (UTC)")
    st.dataframe(pics)

# ---------- Santé des données ----------
with tab2:
    st.subheader("Fraîcheur et complétude")
    try:
        h = load_health()
        now = pd.Timestamp.now()
        last_air = pd.Timestamp(h["air"]["last_ingest"])
        last_meteo = pd.Timestamp(h["meteo"]["last_ingest"])
        age_air = (now - last_air).total_seconds() / 3600
        age_meteo = (now - last_meteo).total_seconds() / 3600

        def statut(age_h: float) -> str:
            if age_h < 3:
                return "OK (< 3 h)"
            if age_h < 6:
                return "Avertissement (3 à 6 h)"
            return "Périmée (> 6 h)"

        f1, f2 = st.columns(2)
        f1.metric("raw_air : dernier chargement", str(last_air)[:16], statut(age_air))
        f2.metric("raw_meteo : dernier chargement", str(last_meteo)[:16], statut(age_meteo))
        st.caption(
            "Mêmes seuils que `dbt source freshness` (warn 3 h, error 6 h). "
            "L'âge est calculé avec l'heure locale du PC : un décalage de fuseau est possible."
        )
        st.write(f"Lignes raw_air : {int(h['air']['n'])} | raw_meteo : {int(h['meteo']['n'])}")
    except Exception as e:
        st.warning(f"Fraîcheur indisponible : {e}")

    st.write("Valeurs manquantes par colonne (table finale)")
    nulls = (df.isna().mean() * 100).round(1).rename("% nulls").to_frame()
    st.dataframe(nulls)

    st.write("Couverture par ville")
    cov = df.groupby("city_name").agg(
        lignes=("observed_at", "count"),
        premiere=("observed_at", "min"),
        derniere=("observed_at", "max"),
    )
    st.dataframe(cov)

    st.info(
        "Les résultats des tests dbt (`dbt build`) sont visibles dans le terminal, "
        "la CI GitHub Actions et `dbt docs serve`."
    )