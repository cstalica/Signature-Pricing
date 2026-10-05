import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Direct API Inspector",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ Signature Aviation — Direct REST API Pricing Inspector")
st.markdown("Queries Signature Aviation's direct REST endpoint with deep payload parsing across stations.")

# Station Mapping & Account Details
ALL_STATIONS = {
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "OPF": {"baseId": "L26", "baseCode": "OPF"},
    "MIA": {"baseId": "L23", "baseCode": "MIA"},
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

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
show_debug = st.sidebar.checkbox("Enable Raw API Debug Panel", value=True)


def extract_price_val(item, keys):
    """Extracts a numeric or string price value from a dictionary given possible keys."""
    if not isinstance(item, dict):
        return None
    for k in keys:
        for item_k, val in item.items():
            if item_k.lower() == k.lower() and val is not None:
                try:
                    return f"${float(val):.2f}"
                except (ValueError, TypeError):
                    if str(val).strip():
                        return str(val)
    return None


def extract_signature_pricing(data):
    """Deep-parses Signature REST API JSON payload regardless of nesting level or FBO-specific key variations."""
    extracted = {
        "retail_price": "N/A",
        "jet_a_additive": "N/A",
        "avgas_100ll": "N/A",
        "handling": "N/A",
        "waiver_min_gallons": "N/A",
        "infra": "N/A",
        "gpu": "N/A",
        "hangar": "N/A",
        "lav": "N/A"
    }

    if not data:
        return extracted

    # Flatten nested payload root containers
    root = data
    if isinstance(root, dict):
        for wrapper in ["data", "result", "payload", "pricingDetail", "services"]:
            if wrapper in root and isinstance(root[wrapper], (dict, list)):
                root = root[wrapper]

    # Gather items list
    items_list = []
    if isinstance(root, list):
        items_list = root
    elif isinstance(root, dict):
        for k, v in root.items():
            if isinstance(v, list):
                items_list.extend(v)

    # 1. Parse Fuel Pricing Items
    for item in items_list:
        if not isinstance(item, dict):
            continue
        code = str(item.get("serviceCode", item.get("code", item.get("productCode", "")))).upper()
        name = str(item.get("serviceName", item.get("name", item.get("productName", "")))).upper()
        
        price_val = extract_price_val(item, ["retailPrice", "retail", "customerPrice", "price", "netPrice", "rate", "unitPrice"])
        
        if not price_val:
            continue

        if "JET A" in name and "ADDITIVE" in name:
            extracted["jet_a_additive"] = price_val
        elif "JET A" in name or "JET A" in code:
            if extracted["retail_price"] == "N/A":
                extracted["retail_price"] = price_val
        elif "100LL" in name or "AVGAS" in name:
            extracted["avgas_100ll"] = price_val
        elif any(k in code or k in name for k in ["HANDLING", "RAMP", "FACILITY"]):
            extracted["handling"] = price_val
            waiver_gal = item.get("waiverMinGallons", item.get("waiverGallons", item.get("minFuelWaiver")))
            if waiver_gal:
                extracted["waiver_min_gallons"] = f"{waiver_gal} gal"
        elif any(k in code or k in name for k in ["INFRASTRUCTURE", "INFRA", "SECURITY"]):
            extracted["infra"] = price_val
        elif any(k in code or k in name for k in ["GPU", "GROUND POWER", "POWER"]):
            extracted["gpu"] = price_val

    return extracted


def fetch_signature_pricing_api(icao, aircraft_list, date_val):
    """Executes REST API queries and captures raw payloads for debugging."""
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    raw_responses = {}
    
    station_info = ALL_STATIONS.get(icao, {"baseId": "", "baseCode": icao})
    
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.signatureaviation.com/locations/{icao}?fboDetailId={station_info['baseId']}",
        "Origin": "https://www.signatureaviation.com"
    }

    for reg in aircraft_list:
        clean_reg = reg.strip().upper()
        
        api_url = (
            f"https://new-prod-api.signatureaviation.com/api/rest/pricing/services/discount?"
            f"baseId={station_info['baseId']}&baseCode={station_info['baseCode']}&pricingDate={encoded_date}&"
            f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
            f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
        )
        
        response_json = {}
        try:
            res = session.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                response_json = res.json()
            else:
                response_json = {"error": f"HTTP {res.status_code}", "text": res.text[:200]}
        except Exception as e:
            response_json = {"error": str(e)}

        raw_responses[clean_reg] = response_json
        parsed = extract_signature_pricing(response_json)
        
        records.append({
            "ICAO": icao,
            "Aircraft Reg": clean_reg,
            "Date": formatted_date,
            "Jet A": parsed["retail_price"],
            "Jet A (Additive)": parsed["jet_a_additive"],
            "Avgas 100LL": parsed["avgas_100ll"],
            "Handling Fee": parsed["handling"],
            "Waiver Min Fuel": parsed["waiver_min_gallons"],
            "Infrastructure Fee": parsed["infra"],
            "GPU Fee": parsed["gpu"]
        })
        
    return records, raw_responses


# Execution
with st.spinner(f"Fetching live API data for {selected_station_icao}..."):
    records, raw_responses = fetch_signature_pricing_api(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Pricing Table — {selected_station_icao}")
df_results = pd.DataFrame(records)

# Display Data Table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Export
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download {selected_station_icao} Pricing CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# Raw API Debug Panel
if show_debug:
    st.markdown("---")
    st.subheader("🔍 Raw API Response Inspector")
    for reg, payload in raw_responses.items():
        with st.expander(f"Raw JSON for {reg} at {selected_station_icao}"):
            st.json(payload)