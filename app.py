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
    """Launches Playwright Chromium, triggers modal rendering, and parses active DOM elements."""
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

            # Click 'View Prices' button to open modal overlay if closed
            view_prices_btn = page.locator("text='View Prices'").first
            if view_prices_btn.is_visible():
                view_prices_btn.click()
                page.wait_for_timeout(2500)

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

                # Update registration input if field is present in modal
                reg_input = page.locator("input[placeholder*='Aircraft Registration']").first
                if reg_input.is_visible():
                    reg_input.fill(clean_reg)
                    
                    # Click 'View' button or press Enter to trigger update
                    view_btn = page.locator("button:has-text('View')").first
                    if view_btn.is_visible():
                        view_btn.click()
                    else:
                        reg_input.press("Enter")
                    page.wait_for_timeout(3000)

                # Extract Jet A Prices using Playwright locators
                jet_a_card = page.locator("div").filter(has_text="JET A").filter(has_text="6.").first
                if not jet_a_card.is_visible():
                    jet_a_card = page.locator("div").filter(has_text="JET A").first

                if jet_a_card.is_visible():
                    card_text = jet_a_card.inner_text()
                    lines = [line.strip() for line in card_text.split("\n") if line.strip()]
                    nums = [l.replace("$", "") for l in lines if l.replace(".", "").isdigit()]
                    if len(nums) >= 2:
                        data["Contract Jet A"] = f"${nums[0]}"
                        data["Retail Jet A"] = f"${nums[1]}"
                    elif len(nums) == 1:
                        data["Contract Jet A"] = f"${nums[0]}"

                # Extract Handling Fee
                handling_card = page.locator("div").filter(has_text="Handling Fee").last
                if handling_card.is_visible():
                    txt = handling_card.inner_text()
                    for word in txt.split():
                        clean = word.replace(",", "").replace("$", "")
                        if clean.replace(".", "").isdigit() and len(clean) >= 3:
                            data["Handling Fee"] = f"${clean}"
                            break
                    if "waived with" in txt.lower():
                        parts = txt.lower().split("waived with")[1].split()
                        if len(parts) >= 3:
                            data["Waiver Min Fuel"] = f"{parts[1]} {parts[2].upper()}"

                # Extract Infrastructure Fee
                infra_card = page.locator("div").filter(has_text="Infrastructure Fee").last
                if infra_card.is_visible():
                    for word in infra_card.inner_text().split():
                        clean = word.replace(",", "").replace("$", "")
                        if clean.replace(".", "").isdigit():
                            data["Infrastructure Fee"] = f"${clean}"
                            break

                # Extract Ground Power Unit (GPU)
                gpu_card = page.locator("div").filter(has_text="Ground Power Unit").first
                if gpu_card.is_visible():
                    for word in gpu_card.inner_text().split():
                        clean = word.replace(",", "").replace("$", "")
                        if clean.replace(".", "").isdigit():
                            data["GPU"] = f"${clean}"
                            break

                # Extract Lavatory Service
                lav_card = page.locator("div").filter(has_text="Lavatory Service").last
                if lav_card.is_visible():
                    for word in lav_card.inner_text().split():
                        clean = word.replace(",", "").replace("$", "")
                        if clean.replace(".", "").isdigit():
                            data["Lav Service"] = f"${clean}"
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