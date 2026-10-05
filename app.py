import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fleet Tracker",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Fuel Pricing Array Inspector")
st.markdown("Extracts and displays live `fuelPricing` and volume tiers directly from Signature's API schema payloads.")

# Default Options & Mapping Constants
ALL_STATIONS = {
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"},
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "MIA": {"baseId": "L23", "baseCode": "MIA"}
}
DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Fixed Account Credentials
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

station_mode = st.sidebar.radio("Airport Selection Mode", ["Single Airport", "All Airports"])
if station_mode == "Single Airport":
    selected_station = st.sidebar.selectbox("Select Airport ICAO", list(ALL_STATIONS.keys()), index=0)
    stations_to_query = [selected_station]
else:
    stations_to_query = list(ALL_STATIONS.keys())

aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["Single Aircraft", "All Aircraft (Fleet)"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())

st.sidebar.markdown("---")
enable_debug = st.sidebar.checkbox("Enable Live API Debug Inspector", value=True)

def extract_signature_pricing(data):
    extracted = {
        "service_code": "JET-A", "service_name": "Jet A", "retail_price": "N/A",
        "jet_a_tier1": "N/A", "jet_a_tier2": "N/A", "jet_a_tier3": "N/A",
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "special_event": "N/A", "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    fuel_items = data.get("fuelPricing", []) if isinstance(data, dict) else []
    target_fuel_item = None
    
    for item in fuel_items:
        code = str(item.get("serviceCode", "")).upper()
        name = str(item.get("serviceName", "")).lower()
        if "additive" not in name and "ADDITIVE" not in code and "100LL" not in code:
            target_fuel_item = item
            break
            
    if not target_fuel_item and fuel_items:
        target_fuel_item = fuel_items[0]

    if target_fuel_item:
        if target_fuel_item.get("retailPrice"):
            extracted["retail_price"] = f"{float(target_fuel_item.get('retailPrice')):.2f}"
        
        tiers = target_fuel_item.get("priceTiers", [])
        if isinstance(tiers, list) and len(tiers) > 0:
            for idx, tier in enumerate(sorted(tiers, key=lambda x: x.get("minQuantity", 0))):
                p = tier.get("price")
                if p is not None:
                    if idx == 0: extracted["jet_a_tier1"] = f"{float(p):.2f}"
                    elif idx == 1: extracted["jet_a_tier2"] = f"{float(p):.2f}"
                    elif idx == 2: extracted["jet_a_tier3"] = f"{float(p):.2f}"
        else:
            cust_p = target_fuel_item.get("customerPrice")
            if cust_p is not None:
                extracted["jet_a_tier1"] = f"{float(cust_p):.2f}"

    for s_item in data.get("serviceFees", []) if isinstance(data, dict) else []:
        code = str(s_item.get("serviceCode", "")).upper()
        price = s_item.get("customerPrice")
        if price is not None:
            val_str = f"{float(price):.2f}"
            if "HANDLING" in code:
                extracted["handling"] = val_str
                if s_item.get("waiverMinGallons"):
                    extracted["waiver_min_gallons"] = str(s_item.get("waiverMinGallons"))
            elif "INFRASTRUCTURE" in code: extracted["infra"] = val_str
            elif "GPU" in code: extracted["gpu"] = val_str
            elif "HANGAR" in code: extracted["hangar"] = val_str
            elif "LAV" in code: extracted["lav"] = val_str

    return extracted

def fetch_live_signature_pricing(stations_list, aircraft_list, date_val):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    
    for icao in stations_list:
        clean_icao = icao.strip().upper()
        station_info = ALL_STATIONS.get(clean_icao, {"baseId": "L23", "baseCode": clean_icao})
        
        for reg in aircraft_list:
            clean_reg = reg.strip().upper()
            if not clean_reg: continue
                
            full_url = (
                f"https://new-prod-api.signatureaviation.com/api/rest/pricing/services/discount?"
                f"baseId={station_info['baseId']}&baseCode={station_info['baseCode']}&pricingDate={encoded_date}&"
                f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
                f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
            )
            
            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            response_json = {}
            try:
                res = requests.get(full_url, headers=headers, timeout=3)
                if res.status_code == 200:
                    response_json = res.json()
            except Exception:
                pass

            parsed = extract_signature_pricing(response_json)
            records.append({
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Retail Price": parsed["retail_price"],
                "Jet A 0-500 GLL": parsed["jet_a_tier1"],
                "Jet A 501-1200 GLL": parsed["jet_a_tier2"],
                "Jet A 1201+ GLL": parsed["jet_a_tier3"],
                "Handling Fee": parsed["handling"],
                "Waiver Min GLL": parsed["waiver_min_gallons"],
                "Infrastructure Fee": parsed["infra"],
                "GPU": parsed["gpu"],
                "Hangar": parsed["hangar"] if parsed["hangar"] != "0.00" else "Call FBO",
                "Lav Service": parsed["lav"]
            })
    return records

# Fetch and display current records
records = fetch_live_signature_pricing(stations_to_query, aircraft_to_query, selected_date)

st.subheader("📊 Full Processed Pricing Table")
df_results = pd.DataFrame(records)

# Display table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Download Button
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Pricing Table as CSV",
    data=csv_data,
    file_name=f"signature_fuel_pricing_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)