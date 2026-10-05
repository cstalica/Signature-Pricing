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
st.markdown("Queries live Signature FBO rate schedules using Playwright browser automation.")

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
    """Launches Playwright Chromium to intercept network payloads and extract rendered DOM pricing."""
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
            # Navigate to base FBO URL
            page.goto(station_info["fboUrl"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Open pricing modal if 'View Prices' button is visible
            if page.is_visible("text=View Prices"):
                page.click("text=View Prices")
                page.wait_for_timeout(2000)

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

                # Update tail number if input field is visible
                input_field = page.query_selector("input[placeholder*='Aircraft Registration']") or page.query_selector("input[value*='N']")
                if input_field:
                    input_field.fill(clean_reg)
                    input_field.press("Enter")
                    page.wait_for_timeout(2500)

                # Extract rendered page DOM
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")

                # Parse Jet A Pricing
                jet_a_card = soup.find(lambda tag: tag.name == "div" and "JET A" in tag.text.upper() and ("6." in tag.text or "7." in tag.text or "8." in tag.text or "9." in tag.text or "10." in tag.text or "11." in tag.text))
                if jet_a_card:
                    card_text = jet_a_card.get_text()
                    prices = [w.strip() for w in card_text.split() if w.strip().replace(".", "").isdigit()]
                    if len(prices) >= 2:
                        data["Contract Jet A"] = f"${prices[0]}"
                        data["Retail Jet A"] = f"${prices[1]}"
                    elif len(prices) == 1:
                        data["Contract Jet A"] = f"${prices[0]}"

                # Parse Handling Fee & Waiver
                handling_node = soup.find(text=lambda t: t and "Handling Fee" in t)
                if handling_node:
                    parent = handling_node.find_parent("div")
                    if parent:
                        parent_text = parent.get_text()
                        for token in parent_text.split():
                            clean_token = token.replace(",", "").replace("$", "")
                            if clean_token.replace(".", "").isdigit() and len(clean_token) >= 3:
                                data["Handling Fee"] = f"${clean_token}"
                                break
                        if "waived with" in parent_text.lower():
                            words = parent_text.lower().split("waived with")[1].split()
                            data["Waiver Min Fuel"] = f"{words[1]} {words[2]}" if len(words) >= 3 else "See Terms"

                # Parse Ancillaries
                for fee_key, field_name in [("Infrastructure Fee", "Infrastructure Fee"), ("Ground Power Unit", "GPU"), ("Lavatory Service", "Lav Service")]:
                    node = soup.find(text=lambda t: t and fee_key in t)
                    if node:
                        p_div = node.find_parent("div")
                        if p_div:
                            for token in p_div.get_text().split():
                                clean_token = token.replace(",", "").replace("$", "")
                                if clean_token.replace(".", "").isdigit():
                                    data[field_name] = f"${clean_token}"
                                    break

                records.append(data)

        except Exception as e:
            st.error(f"Playwright Automation Error: {e}")
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
with st.spinner(f"Running automated browser session for {selected_station_icao}..."):
    records = scrape_signature_data(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Scraped Data — {selected_station_icao}")
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