import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API Inspector",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live API Pricing Inspector")
st.markdown("Select an airport to fetch real-time `fuelPricing` and `serviceFees` directly from Signature's API.")

# Default Options & Mapping Constants
ALL_STATIONS = {
    "MIA": {"baseId": "L23", "baseCode": "MIA"},
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Fixed Account Credentials
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

# Dynamic Airport Selection
selected_station_icao = st.sidebar.selectbox(
    "Select Airport ICAO", 
    list(ALL_STATIONS.keys()), 
    index=0
)

aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["All Aircraft (Fleet)", "Single Aircraft"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())


def extract_signature_pricing(data):
    """Parses raw API JSON response into structured row dictionary."""
    extracted = {
        "retail_price": "N/A",
        "jet_a_tier1": "N/A", "jet_a_tier2": "N/A", "jet_a_tier3": "N/A",
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    if not isinstance(data, dict):
        return extracted

    # Extract Jet A Pricing & Volume Tiers
    fuel_items = data.get("fuelPricing", [])
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
            extracted["retail_price"] = f"${float(target_fuel_item.get('retailPrice')):.2f}"
        
        tiers = target_fuel_item.get("priceTiers", [])
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted(tiers, key=lambda x: x.get("minQuantity", 0))
            for idx, tier in enumerate(sorted_tiers):
                p = tier.get("price")
                if p is not None:
                    if idx == 0: extracted["jet_a_tier1"] = f"${float(p):.2f}"
                    elif idx == 1: extracted["jet_a_tier2"] = f"${float(p):.2f}"
                    elif idx == 2: extracted["jet_a_tier3"] = f"${float(p):.2f}"
        else:
            cust_p = target_fuel_item.get("customerPrice")
            if cust_p is not None:
                extracted["jet_a_tier1"] = f"${float(cust_p):.2f}"

    # Extract Service Fees
    for s_item in data.get("serviceFees", []):
        code = str(s_item.get("serviceCode", "")).upper()
        price = s_item.get("customerPrice")
        if price is not None:
            val_str = f"${float(price):.2f}"
            if "HANDLING" in code:
                extracted["handling"] = val_str
                if s_item.get("waiverMinGallons"):
                    extracted["waiver_min_gallons"] = f"{s_item.get('waiverMinGallons')} gal"
            elif "INFRASTRUCTURE" in code: 
                extracted["infra"] = val_str
            elif "GPU" in code: 
                extracted["gpu"] = val_str
            elif "HANGAR" in code: 
                extracted["hangar"] = val_str
            elif "LAV" in code: 
                extracted["lav"] = val_str

    return extracted


def fetch_live_signature_pricing(icao, aircraft_list, date_val):
    """Fetches real-time pricing data directly from Signature's REST API for a given airport."""
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    
    station_info = ALL_STATIONS.get(icao, {"baseId": "L23", "baseCode": icao})
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json"
    }

    for reg in aircraft_list:
        clean_reg = reg.strip().upper()
        
        full_url = (
            f"https://new-prod-api.signatureaviation.com/api/rest/pricing/services/discount?"
            f"baseId={station_info['baseId']}&baseCode={station_info['baseCode']}&pricingDate={encoded_date}&"
            f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
            f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
        )
        
        response_json = {}
        try:
            res = requests.get(full_url, headers=headers, timeout=5)
            if res.status_code == 200:
                response_json = res.json()
            else:
                st.warning(f"API returned status code {res.status_code} for {icao} ({clean_reg})")
        except Exception as e:
            st.error(f"Failed to connect to API for {clean_reg}: {e}")

        parsed = extract_signature_pricing(response_json)
        
        records.append({
            "ICAO": icao,
            "Aircraft Reg": clean_reg,
            "Date": formatted_date,
            "Retail Jet A": parsed["retail_price"],
            "Jet A Tier 1": parsed["jet_a_tier1"],
            "Jet A Tier 2": parsed["jet_a_tier2"],
            "Jet A Tier 3": parsed["jet_a_tier3"],
            "Handling Fee": parsed["handling"],
            "Waiver Min Fuel": parsed["waiver_min_gallons"],
            "Infrastructure Fee": parsed["infra"],
            "GPU": parsed["gpu"],
            "Hangar": parsed["hangar"] if parsed["hangar"] != "$0.00" else "Call FBO",
            "Lav Service": parsed["lav"]
        })
        
    return records


# Fetch fresh data whenever user changes selector
with st.spinner(f"Querying live API for {selected_station_icao}..."):
    records = fetch_live_signature_pricing(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Pricing Table — {selected_station_icao}")
df_results = pd.DataFrame(records)

# Display Table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Export
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Export {selected_station_icao} Data to CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)