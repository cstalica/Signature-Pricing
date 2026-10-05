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
    """Parses raw Signature REST API JSON payload directly."""
    extracted = {
        "Retail Jet A": "N/A",
        "Contract Jet A": "N/A",
        "Handling Fee": "N/A",
        "Waiver Min Fuel": "N/A",
        "Infrastructure Fee": "N/A",
        "GPU": "N/A",
        "Lav Service": "N/A"
    }
    
    if not isinstance(json_data, dict):
        return extracted

    payload = json_data.get("data", json_data)
    if isinstance(payload, dict) and "result" in payload:
        payload = payload["result"]

    # Extract Fuel Pricing
    fuel_items = payload.get("fuelPricing", payload.get("fuelPrices", []))
    for item in fuel_items:
        name = str(item.get("serviceName", item.get("name", ""))).upper()
        if "JET A" in name and "ADDITIVE" not in name:
            retail = item.get("retailPrice", item.get("retail"))
            cust = item.get("customerPrice", item.get("price"))
            if retail is not None:
                extracted["Retail Jet A"] = f"${float(retail):.2f}"
            if cust is not None:
                extracted["Contract Jet A"] = f"${float(cust):.2f}"
            break

    # Extract Service Fees
    service_items = payload.get("serviceFees", payload.get("services", []))
    for s in service_items:
        code = str(s.get("serviceCode", s.get("code", ""))).upper()
        name = str(s.get("serviceName", s.get("name", ""))).upper()
        price = s.get("customerPrice", s.get("price", s.get("amount")))
        
        if price is not None:
            val_str = f"${float(price):.2f}"
            if "HANDLING" in code or "HANDLING" in name:
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
        # Launch Chromium with anti-bot detection flags
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
        page = context.new_page()

        # Capture intercepted API payloads
        captured_payloads = {}

        def handle_response(response):
            if "pricing" in response.url or "discount" in response.url:
                try:
                    if response.status == 200:
                        body = response.json()
                        captured_payloads[response.url] = body
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            # Navigate to station page
            page.goto(station_info["fboUrl"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Trigger pricing modal
            view_prices_btn = page.get_by_role("button", name="View Prices")
            if not view_prices_btn.is_visible():
                view_prices_btn = page.locator("text='View Prices'").first

            if view_prices_btn.is_visible():
                view_prices_btn.click()
                page.wait_for_timeout(3000)

            for reg in aircraft_list:
                clean_reg = reg.strip().upper()

                # Input aircraft registration into modal field
                reg_input = page.locator("input[placeholder*='Aircraft Registration']").first
                if not reg_input.is_visible():
                    reg_input = page.locator("input[type='text']").first

                if reg_input.is_visible():
                    reg_input.fill(clean_reg)
                    
                    # Submit query
                    view_btn = page.get_by_role("button", name="View")
                    if view_btn.is_visible():
                        view_btn.click()
                    else:
                        reg_input.press("Enter")

                    page.wait_for_timeout(3500)

                # Parse intercepted JSON responses if captured
                parsed_result = None
                for url, json_body in captured_payloads.items():
                    if clean_reg.lower() in url.lower() or "pricing" in url:
                        parsed_result = parse_api_json_payload(json_body)
                        break

                if not parsed_result:
                    parsed_result = {
                        "Retail Jet A": "N/A", "Contract Jet A": "N/A", "Handling Fee": "N/A",
                        "Waiver Min Fuel": "N/A", "Infrastructure Fee": "N/A", "GPU": "N/A", "Lav Service": "N/A"
                    }

                records.append({
                    "ICAO": icao,
                    "Aircraft Reg": clean_reg,
                    "Date": formatted_date,
                    **parsed_result
                })

        except Exception as e:
            st.error(f"Playwright Browser Error: {e}")
            for reg in aircraft_list:
                records.append({
                    "ICAO": icao, "Aircraft Reg": reg, "Date": formatted_date,
                    "Retail Jet A": "N/A", "Contract Jet A": "N/A", "Handling Fee": "N/A",
                    "Waiver Min Fuel": "N/A", "Infrastructure Fee": "N/A", "GPU": "N/A", "Lav Service": "N/A"
                })
        finally:
            browser.close()

    return records


# Render Streamlit App
with st.spinner(f"Intercepting live API payload for {selected_station_icao}..."):
    records = scrape_signature_data(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live API Data Table — {selected_station_icao}")
df_results = pd.DataFrame(records)
st.dataframe(df_results, use_container_width=True, hide_index=True)

# Export Option
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download {selected_station_icao} Pricing CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)