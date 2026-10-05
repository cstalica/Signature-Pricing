import os
import subprocess
import streamlit as st
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

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
st.markdown("Queries live Signature FBO rate schedules using Playwright browser automation to bypass Cloudflare protection.")

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


def scrape_signature_data(icao, aircraft_list, target_date):
    """Launches Playwright headless Chromium to bypass Cloudflare and parse live DOM elements."""
    station_info = ALL_STATIONS.get(icao, ALL_STATIONS["OPF"])
    formatted_date = target_date.strftime("%m/%d/%Y")
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            # Navigate to FBO page
            page.goto(station_info["fboUrl"], wait_until="networkidle", timeout=30000)

            for reg in aircraft_list:
                clean_reg = reg.strip().upper()
                data = {
                    "ICAO": icao,
                    "Aircraft Reg": clean_reg,
                    "Date": formatted_date,
                    "Retail Jet A": "N/A",
                    "Contract Jet A": "N/A",
                    "Handling Fee": "N/A",
                    "Waiver Min Fuel": "N/A",
                    "Infrastructure Fee": "N/A",
                    "GPU": "N/A",
                    "Lav Service": "N/A"
                }

                # Interact with aircraft selection modal if present
                if page.is_visible("input[placeholder*='Aircraft Registration']"):
                    page.fill("input[placeholder*='Aircraft Registration']", clean_reg)
                    page.click("button:has-text('View')")
                    page.wait_for_timeout(2000)

                # Extract rendered page HTML
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")

                # Parse Jet A Pricing
                jet_a_elem = soup.find(text=lambda t: t and "JET A" in t.upper())
                if jet_a_elem:
                    card = jet_a_elem.find_parent("div")
                    if card:
                        texts = [t.strip() for t in card.find_all(text=True) if t.strip()]
                        dollar_vals = [t for t in texts if t.replace(".", "").isdigit() or "$" in t]
                        if len(dollar_vals) >= 2:
                            data["Contract Jet A"] = f"${dollar_vals[0].replace('$', '')}"
                            data["Retail Jet A"] = f"${dollar_vals[1].replace('$', '')}"
                        elif len(dollar_vals) == 1:
                            data["Contract Jet A"] = f"${dollar_vals[0].replace('$', '')}"

                # Parse Handling Fee & Waiver Threshold
                handling_elem = soup.find(text=lambda t: t and "Handling Fee" in t)
                if handling_elem:
                    card = handling_elem.find_parent("div")
                    if card:
                        card_text = card.get_text()
                        for word in card_text.split():
                            if "$" in word or word.replace(",", "").replace(".", "").isdigit():
                                data["Handling Fee"] = word.strip()
                                break
                        if "waived with" in card_text.lower():
                            parts = card_text.lower().split("waived with")
                            if len(parts) > 1:
                                data["Waiver Min Fuel"] = parts[1].split()[2] + " gal" if len(parts[1].split()) > 2 else "See Terms"

                # Parse Ancillary Fees
                infra_elem = soup.find(text=lambda t: t and "Infrastructure Fee" in t)
                if infra_elem:
                    card = infra_elem.find_parent("div")
                    if card:
                        for word in card.get_text().split():
                            if "$" in word or word.replace(",", "").replace(".", "").isdigit():
                                data["Infrastructure Fee"] = word.strip()
                                break

                gpu_elem = soup.find(text=lambda t: t and "Ground Power Unit" in t)
                if gpu_elem:
                    card = gpu_elem.find_parent("div")
                    if card:
                        for word in card.get_text().split():
                            if "$" in word or word.replace(",", "").replace(".", "").isdigit():
                                data["GPU"] = word.strip()
                                break

                lav_elem = soup.find(text=lambda t: t and "Lavatory Service" in t)
                if lav_elem:
                    card = lav_elem.find_parent("div")
                    if card:
                        for word in card.get_text().split():
                            if "$" in word or word.replace(",", "").replace(".", "").isdigit():
                                data["Lav Service"] = word.strip()
                                break

                records.append(data)

        except Exception as e:
            st.error(f"Playwright Execution Error for {icao}: {e}")
            for reg in aircraft_list:
                records.append({
                    "ICAO": icao, "Aircraft Reg": reg, "Date": formatted_date,
                    "Retail Jet A": "N/A", "Contract Jet A": "N/A", "Handling Fee": "N/A",
                    "Waiver Min Fuel": "N/A", "Infrastructure Fee": "N/A", "GPU": "N/A", "Lav Service": "N/A"
                })
        finally:
            browser.close()

    return records


# Render App Results
with st.spinner(f"Querying live pricing for {selected_station_icao} via Playwright..."):
    records = scrape_signature_data(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Data Table — {selected_station_icao}")
df_results = pd.DataFrame(records)

# Display Table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# Export Button
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download {selected_station_icao} Pricing CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)