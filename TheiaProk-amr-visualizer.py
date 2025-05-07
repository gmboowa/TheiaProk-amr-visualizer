#!/usr/bin/env python3

import pandas as pd
import plotly.graph_objects as go
import pycountry
from geopy.geocoders import Nominatim
from time import sleep
import argparse

# --- Argument Parser ---
parser = argparse.ArgumentParser(description="Visualize TB resistance patterns on a world map.")
parser.add_argument("-i", "--input", required=True, help="Path to input TSV file with TB data.")
args = parser.parse_args()

# --- Load and process data ---
df = pd.read_csv(args.input, sep="\t")
df = df.dropna(subset=["tbprofiler_dr_type", "Country_of_sample_collection"])

# Total tested per country
total_per_country = df.groupby("Country_of_sample_collection").size().reset_index(name="total_samples")

# Count of each resistance type per country
counts = df.groupby(["Country_of_sample_collection", "tbprofiler_dr_type"]).size().reset_index(name="count")
counts = counts.merge(total_per_country, on="Country_of_sample_collection")
counts["percent"] = (counts["count"] / counts["total_samples"]) * 100

# Assign ISO Alpha-3 codes
def get_iso3(name):
    try:
        return pycountry.countries.lookup(name).alpha_3
    except:
        return None

counts["iso_alpha"] = counts["Country_of_sample_collection"].apply(get_iso3)
counts = counts.dropna(subset=["iso_alpha"])

# Add coordinates with jitter
jitter_map = {
    "Sensitive": 0.0,
    "RR-TB": 0.2,
    "MDR-TB": 0.4,
    "Pre-XDR-TB": 0.6,
    "HR-TB": 0.8,
    "XDR-TB": 1.0,
    "Other": 1.2
}

# --- Geolocation with overrides ---
geolocator = Nominatim(user_agent="tb_bubble_map")
country_coords = {}
for country in counts["Country_of_sample_collection"].unique():
    try:
        if country == "Georgia":
            country_coords[country] = {"lat": 42.3154, "lon": 43.3569}
            continue
        if country == "Sudan":
            country_coords[country] = {"lat": 12.8628, "lon": 30.2176}
            continue
        location = geolocator.geocode(country)
        if location:
            country_coords[country] = {"lat": location.latitude, "lon": location.longitude}
    except:
        pass
    sleep(1)

def apply_coords(row):
    coords = country_coords.get(row["Country_of_sample_collection"], {"lat": 0.0, "lon": 30.0})
    jitter = jitter_map.get(row["tbprofiler_dr_type"], 0.0)
    return pd.Series({"lat": coords["lat"], "lon": coords["lon"] + jitter})

counts[["lat", "lon"]] = counts.apply(apply_coords, axis=1)

# --- Select relevant types ---
selected_types = ["Sensitive", "Other", "HR-TB", "RR-TB", "MDR-TB", "Pre-XDR-TB", "XDR-TB"]
counts = counts[counts["tbprofiler_dr_type"].isin(selected_types)]

# --- Color Map ---
color_map = {
    "Sensitive": "#008000",
    "Other": "#333333",
    "HR-TB": "#FFD700",
    "RR-TB": "#FF8C00",
    "MDR-TB": "#9370DB",
    "Pre-XDR-TB": "#F08080",
    "XDR-TB": "#FF0000"
}

# --- Footnote ---
footnote = (
    "<b>Footnote:</b><br><br>"
    "<span style='color:#008000'><b>Sensitive</b></span>:<br>No drug<br>resistance<br><br>"
    "<span style='color:#333333'><b>Other</b></span>:<br>Other<br>resistance patterns<br><br>"
    "<span style='color:#FFD700'><b>HR-TB</b></span>:<br>Isoniazid-<br>resistant TB<br><br>"
    "<span style='color:#FF8C00'><b>RR-TB</b></span>:<br>Rifampicin-<br>resistant TB<br><br>"
    "<span style='color:#9370DB'><b>MDR-TB</b></span>:<br>Resistant to Isoniazid<br>& Rifampicin<br><br>"
    "<span style='color:#F08080'><b>Pre-XDR-TB</b></span>:<br>MDR-TB + resistance<br>to a Fluoroquinolone<br><br>"
    "<span style='color:#FF0000'><b>XDR-TB</b></span>:<br>MDR-TB + resistance<br>to Fluoroquinolone<br>& one Group A drug"
)

# --- Plotly ---
fig = go.Figure()
max_percent = counts["percent"].max()

for drug in selected_types:
    data = counts[counts["tbprofiler_dr_type"] == drug]
    fig.add_trace(go.Scattergeo(
        lon=data["lon"],
        lat=data["lat"],
        marker=dict(
            size=data["percent"],
            color=color_map.get(drug, "gray"),
            line=dict(width=0.5, color="white"),
            sizemode="area",
            sizeref=2. * max_percent / (40. ** 2),
            sizemin=4
        ),
        name=drug,
        hovertemplate=(
            "<b>Country:</b> %{customdata[0]}<br>" +
            "<b>Resistance Type:</b> %{customdata[1]}<br>" +
            "<b>Count:</b> %{customdata[2]}<br>" +
            "<b>Total Samples:</b> %{customdata[3]}<br>" +
            "<b>Percent:</b> %{customdata[4]:.1f}%<extra></extra>"
        ),
        text=[f"{p:.1f}%" for p in data["percent"]],
        textposition="middle center",
        customdata=data[[
            "Country_of_sample_collection", "tbprofiler_dr_type", "count", "total_samples", "percent"
        ]].values,
        showlegend=True
    ))

fig.update_layout(
    title=dict(
        text="<b>Tuberculosis Drug Resistance Patterns by Country / Region (% of tbprofiler_dr_type)</b>",
        x=0.45,
        xanchor="center",
        font=dict(size=20)
    ),
    height=1000,
    width=1850,
    geo=dict(
        scope="world",
        projection_type="natural earth",
        showland=True,
        landcolor="rgb(230, 230, 230)",
        showcountries=True,
        countrycolor="white",
        domain=dict(x=[0.0, 0.96], y=[0.1, 0.98])
    ),
    legend=dict(
        title=dict(text="<b>Resistance Type&nbsp;&nbsp;&nbsp;</b>", font=dict(size=13, color="black")),
        orientation="v",
        x=0.90,
        y=0.97,
        xanchor="left",
        font=dict(size=14, color="black")
    ),
    annotations=[
        dict(
            text=footnote,
            x=0.90,
            y=0.09,
            xref="paper",
            yref="paper",
            showarrow=False,
            align="left",
            font=dict(size=14, color="black"),
            xanchor="left"
        )
    ],
    margin=dict(r=60, t=60, l=10, b=100)
)

fig.show()
