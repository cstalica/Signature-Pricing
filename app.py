import os
import subprocess
import streamlit as st
import pandas as pd
from datetime import datetime

# Ensure Playwright browser binaries are installed on Streamlit Community Cloud
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Playwright installation check: {e}")

from playwright.sync_api import sync_playwright

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API Inspector",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live API & FBO Inspector")
st.markdown("Queries live Signature FBO rate schedules via Playwright network request interception.")

# Station Mappings
ALL_STATIONS = {
    "MIA": {"baseId": "L23", "baseCode": "MIA", "fboUrl": "https://www.signatureaviation.com/locations/MIA?fboDetailId=L23"},
    "OPF": {"baseId": "L26", "baseCode": "OPF", "fboUrl": "https://www.signatureaviation.com/locations/OPF?fboDetailId=L26"},
    "TMB": {"baseId": "L24", "baseCode": "TMB", "fboUrl": "https://www.signatureaviation.com/locations/TMB?fboDetailId=L24"},
    "BUF": {"baseId": "B70", "baseCode": "BUF", "fboUrl": "https://www.signatureaviation.com/locations/BUF?fboDetailId=B70"},
    "FSM": {"baseId": "B80", "baseCode": "FSM", "fboUrl": "https://www.signatureaviation.com/locations/FSM?fboDetailId=B80"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

selected_station_icao = st.sidebar.selectbox(
    "Select Airport ICAO", 
    list(ALL_STATIONS.keys()), 
    index=1
)

aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["All Aircraft (Fleet)", "Single Aircraft"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())


def parse_api_json_payload(json_data):
    """Parses raw Signature REST API JSON payload safely, handling dicts and lists."""
    extracted = {
        "Retail Jet A": "N/A",
        "Contract Jet A": "N/A",
        "Handling Fee": "N/A",
        "Waiver Min Fuel": "N/A",
        "Infrastructure Fee": "N/A",
        "GPU": "N/A",
        "Lav Service": "N/A"
    }

    if not json_data:
        return extracted

    # Unpack top-level wrappers if present
    payload = json_data
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], (dict, list)):
            payload = payload["data"]
    if isinstance(payload, dict):
        if "result" in payload and isinstance(payload["result"], (dict, list)):
            payload = payload["result"]

    # Extract items depending on whether payload is a dict or a list
    fuel_items = []
    service_items = []

    if isinstance(payload, dict):
        fuel_items = payload.get("fuelPricing", payload.get("fuelPrices", []))
        service_items = payload.get("serviceFees", payload.get("services", []))
    elif isinstance(payload, list):
        fuel_items = payload
        service_items = payload

    if not isinstance(fuel_items, list):
        fuel_items = []
    if not isinstance(service_items, list):
        service_items = []

    # Process Fuel Pricing
    for item in fuel_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("serviceCode", item.get("code", ""))).upper()
        name = str(item.get("serviceName", item.get("name", ""))).upper()
        
        if ("JET A" in name or "JET" in code) and "ADDITIVE" not in name and "100LL" not in name:
            retail = item.get("retailPrice", item.get("retail"))
            cust = item.get("customerPrice", item.get("price"))
            if retail is not None:
                extracted["Retail Jet A"] = f"${float(retail):.2f}"
            if cust is not None:
                extracted["Contract Jet A"] = f"${float(cust):.2f}"
            
            tiers = item.get("priceTiers", item.get("tiers", []))
            if isinstance(tiers, list) and len(tiers) > 0:
                first_tier = tiers[0]
                if isinstance(first_tier, dict):
                    p0 = first_tier.get("price", first_tier.get("customerPrice"))
                    if p0 is not None:
                        extracted["Contract Jet A"] = f"${float(p0):.2f}"
            break

    # Process Service Fees
    for s in service_items:
        if not isinstance(s, dict):
            continue
        code = str(s.get("serviceCode", s.get("code", ""))).upper()
        name = str(s.get("serviceName", s.get("name", ""))).upper()
        price = s.get("customerPrice", s.get("price", s.get("amount")))

        if price is not None:
            try:
                val_str = f"${float(price):.2f}"
            except (ValueError, TypeError):
                val_str = str(price)

            if "HANDLING" in code or "HANDLING" in name or "RAMP" in name:
                extracted["Handling Fee"] = val_str
                waiver = s.get("waiverMinGallons", s.get("waiverGallons"))
                if waiver:
                    extracted["Waiver Min Fuel"] = f"{waiver} gal"
            elif "INFRASTRUCTURE" in code or "INFRASTRUCTURE" in name:
                extracted["Infrastructure Fee"] = val_str
            elif "GPU" in code or "GROUND POWER" in name:
                extracted["GPU"] = val_str
            elif "LAV" in code or "LAVATORY" in name:
                extracted["Lav Service"] = val_str

    return extracted


def scrape_signature_data(icao, aircraft_list, target_date):
    """Launches Playwright Chromium with Stealth flags and intercepts raw API JSON payloads."""
    station_info = ALL_STATIONS.get(icao, ALL_STATIONS["OPF"])
    formatted_date = target_date.strftime("%m/%d/%Y")
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )