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

# Airport Mappings
ALL_STATIONS = {
    "MIA": {"baseId": "L23", "baseCode": "MIA"},
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Account Constants
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

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
    """Robust parser that handles multiple nested structures from Signature's API payload."""
    extracted = {
        "retail_price": "N/A",
        "jet_a_tier1": "N/A", "jet_a_tier2": "N/A", "jet_a_tier3": "N/A",
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    if not isinstance(data, dict):
        return extracted

    # Unnest response payload if encapsulated under 'data' or 'result'
    payload = data.get("data", data) if isinstance(data.get("data"), dict) else data
    payload = payload.get("result", payload) if isinstance(payload.get("result"), dict) else payload

    # Extract Jet A Fuel Pricing
    fuel_items = payload.get("fuelPricing", payload.get("fuelPrices", []))
    target_fuel = None
    
    for item in fuel_items:
        code = str(item.get("serviceCode", item.get("code", ""))).upper()
        name = str(item.get("serviceName", item.get("name", ""))).lower()
        if "additive" not in name and "ADDITIVE" not in code and "100LL" not in code:
            target_fuel = item
            break
            
    if not target_fuel and fuel_items:
        target_fuel = fuel_items[0]

    if target_fuel:
        retail = target_fuel.get("retailPrice", target_fuel.get("retail"))
        if retail is not None:
            extracted["retail_price"] = f"${float(retail):.2f}"
            
        cust_p = target_fuel.get("customerPrice", target_fuel.get("price"))
        if cust_p is not None:
            extracted["jet_a_tier1"] = f"${float(cust_p):.2f}"

        tiers = target_fuel.get("priceTiers", target_fuel.get("tiers", []))
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted(tiers, key=lambda x: float(x.get("minQuantity", x.get("minQty", 0))))
            for idx, tier in enumerate(sorted_tiers):
                p = tier.get("price", tier.get("customerPrice"))
                if p is not None:
                    val = f"${float(p):.2f}"
                    if idx == 0: extracted["jet_a_tier1"] = val
                    elif idx == 1: extracted["jet_a_tier2"] = val
                    elif idx == 2: extracted["jet_a_tier3"] = val

    # Extract Handling & Ancillary Service Fees
    service_fees = payload.get("serviceFees", payload.get("services", []))
    for s_item in service_fees:
        code = str(s_item.get("serviceCode", s_item.get("code", ""))).upper()
        name = str(s_item.get("serviceName", s_item.get("name", ""))).upper()
        price = s_item.get("customerPrice", s_item.get("price", s_item.get("amount")))
        
        if price is not None:
            val_str = f"${float(price):.2f}"
            if "HANDLING" in code or "HANDLING" in name or "RAMP" in name:
                extracted["handling"] = val_str
                waiver_gal = s_item.get("waiverMinGallons", s_item.get("waiverGallons"))
                if waiver_gal:
                    extracted["waiver_min_gallons"] = f"{waiver_gal} gal"
            elif "INFRASTRUCTURE" in code or "INFRASTRUCTURE" in name:
                extracted["infra"] = val_str
            elif "GPU" in code or "GROUND POWER" in name:
                extracted["gpu"] = val_str
            elif "HANGAR" in code or "HANGAR" in name:
                extracted["hangar"] = val_str
            elif "LAV" in code or "LAVATORY" in name:
                extracted["lav"] = val_str

    return extracted


def fetch_live_signature_pricing(icao, aircraft_list, date_val):
    """Executes live network requests with full browser headers to avoid N/A response blocks."""
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    
    station_info = ALL_STATIONS.get(icao, {"baseId": "L23", "baseCode": icao})
    
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.signatureaviation.com/locations/{icao}?fboDetailId={station_info['baseId']}",
        "Origin": "https://www.signatureaviation.com",
        "X-Requested-With": "XMLHttpRequest"
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
            res = session.get(full_url, headers=headers, timeout=6)
            if res.status_code == 200:
                response_json = res.json()
            else:
                # Direct fallback URL if the discount endpoint requires dynamic session cookies
                alt_url = f"https://new-prod-api.signatureaviation.com/api/rest/location/detail/{station_info['baseId']}"
                res_alt = session.get(alt_url, headers=headers, timeout=6)
                if res_alt.status_code == 200:
                    response_json = res_alt.json()
        except Exception as e:
            st.error(f"Network request error for {clean_reg}: {e}")

        parsed = extract_signature_pricing(response_json)
        
        records.append({
            "ICAO": icao,
            "Aircraft Reg": clean_reg,
            "Date": formatted_date,
            "Retail Jet A": parsed["retail_price"],
            "Jet A Contract Price": parsed["jet_a_tier1"],
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


# Render App Results
with st.spinner(f"Querying live API endpoints for {selected_station_icao}..."):
    records = fetch_live_signature_pricing(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Pricing Table — {selected_station_icao}")
df_results = pd.DataFrame(records)

# Display Data Table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Export Button
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download {selected_station_icao} Pricing CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)