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

# Station Mapping & Account Details
ALL_STATIONS = {
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "OPF": {"baseId": "L26", "baseCode": "OPF"},
    "MIA": {"baseId": "L23", "baseCode": "MIA"},
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# UPDATE THESE IF YOU HAVE A BEARER TOKEN FROM THE BROWSER NETWORK TAB
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"
BEARER_TOKEN = "" # Paste session token here if the API returns 401 Unauthorized

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")
selected_station_icao = st.sidebar.selectbox("Select Airport ICAO", list(ALL_STATIONS.keys()), index=0)
aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["All Aircraft (Fleet)", "Single Aircraft"])

if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())
show_debug = st.sidebar.checkbox("Enable Raw API Debug Panel", value=True)

def extract_price_val(item, keys):
    if not isinstance(item, dict): return None
    for k in keys:
        for item_k, val in item.items():
            if item_k.lower() == k.lower() and val is not None:
                try:
                    return f"${float(val):.2f}"
                except:
                    if str(val).strip(): return str(val)
    return None

def extract_signature_pricing(data):
    extracted = {
        "retail_price": "N/A", "jet_a_tier1": "N/A", "jet_a_tier2": "N/A",
        "jet_a_tier3": "N/A", "handling": "N/A", "waiver_min_gallons": "N/A",
        "infra": "N/A", "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    if not data: return extracted

    root = data
    if isinstance(root, dict):
        for wrapper in ["data", "result", "payload", "pricingDetail", "services"]:
            if wrapper in root and isinstance(root[wrapper], (dict, list)):
                root = root[wrapper]

    items_list = []
    if isinstance(root, list):
        items_list = root
    elif isinstance(root, dict):
        for k, v in root.items():
            if isinstance(v, list): items_list.extend(v)

    target_fuel = None
    for item in items_list:
        if not isinstance(item, dict): continue
        code = str(item.get("serviceCode", item.get("code", item.get("productCode", "")))).upper()
        name = str(item.get("serviceName", item.get("name", item.get("productName", "")))).upper()
        if ("JET" in name or "JET" in code) and "100LL" not in name:
            target_fuel = item
            break

    if target_fuel:
        retail = extract_price_val(target_fuel, ["retailPrice", "retail", "listPrice"])
        if retail: extracted["retail_price"] = retail
        cust_p = extract_price_val(target_fuel, ["customerPrice", "price", "netPrice", "rate"])
        if cust_p: extracted["jet_a_tier1"] = cust_p

        tiers = target_fuel.get("priceTiers", target_fuel.get("tiers", target_fuel.get("volumeTiers", [])))
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted([t for t in tiers if isinstance(t, dict)], key=lambda x: float(x.get("minQuantity", x.get("minQty", 0))))
            for idx, tier in enumerate(sorted_tiers):
                p_val = extract_price_val(tier, ["price", "customerPrice", "rate"])
                if p_val:
                    if idx == 0: extracted["jet_a_tier1"] = p_val
                    elif idx == 1: extracted["jet_a_tier2"] = p_val
                    elif idx == 2: extracted["jet_a_tier3"] = p_val

    for item in items_list:
        if not isinstance(item, dict): continue
        code = str(item.get("serviceCode", item.get("code", item.get("productCode", "")))).upper()
        name = str(item.get("serviceName", item.get("name", item.get("productName", "")))).upper()
        fee_val = extract_price_val(item, ["customerPrice", "price", "amount", "netPrice", "rate"])
        
        if fee_val:
            if any(k in code or k in name for k in ["HANDLING", "RAMP", "FACILITY"]):
                extracted["handling"] = fee_val
                waiver = item.get("waiverMinGallons", item.get("waiverGallons"))
                if waiver: extracted["waiver_min_gallons"] = f"{waiver} gal"
            elif any(k in code or k in name for k in ["INFRASTRUCTURE", "INFRA"]):
                extracted["infra"] = fee_val
            elif any(k in code or k in name for k in ["GPU", "GROUND POWER"]):
                extracted["gpu"] = fee_val

    return extracted

def fetch_signature_pricing_api(icao, aircraft_list, date_val):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    raw_responses = {}
    
    station_info = ALL_STATIONS.get(icao, {"baseId": "", "baseCode": icao})
    
    session = requests.Session()
    
    # Fixed Referer to match realistic browser behavior
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.signatureaviation.com",
        "Referer": f"https://www.signatureaviation.com/locations/{icao}"
    }
    
    if BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"

    for reg in aircraft_list:
        clean_reg = reg.strip().upper()
        
        api_url = (
            f"https://new-prod-api.signatureaviation.com/api/rest/pricing/services/discount?"
            f"baseId={station_info['baseId']}&baseCode={station_info['baseCode']}&pricingDate={encoded_date}&"
            f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
            f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
        )
        
        response_json = {}
        error_msg = None
        
        try:
            res = session.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                try:
                    response_json = res.json()
                except Exception:
                    error_msg = "Invalid JSON Format"
                    response_json = {"raw_text": res.text[:500]}
            else:
                # Capture HTTP errors directly
                error_msg = f"HTTP {res.status_code}"
                response_json = {"error": res.text[:500]}
        except requests.exceptions.RequestException as e:
            error_msg = "Connection Error"
            response_json = {"error": str(e)}

        raw_responses[clean_reg] = response_json
        parsed = extract_signature_pricing(response_json)
        
        # Inject the error message directly into the table so it's not silently failing
        if error_msg:
            parsed = {k: error_msg for k in parsed}
            
        records.append({
            "ICAO": icao,
            "Aircraft": clean_reg,
            "Date": formatted_date,
            "Retail Jet A": parsed["retail_price"],
            "Jet A Tier 1": parsed["jet_a_tier1"],
            "Jet A Tier 2": parsed["jet_a_tier2"],
            "Handling": parsed["handling"],
            "Min Fuel": parsed["waiver_min_gallons"],
            "Infra Fee": parsed["infra"],
            "GPU Fee": parsed["gpu"]
        })
        
    return records, raw_responses

with st.spinner(f"Fetching API data for {selected_station_icao}..."):
    records, raw_responses = fetch_signature_pricing_api(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live Pricing Table — {selected_station_icao}")
df_results = pd.DataFrame(records)
st.dataframe(df_results, use_container_width=True, hide_index=True)

if show_debug:
    st.markdown("---")
    st.subheader("🔍 Raw API Response Inspector")
    st.info("Check the payloads below to see exactly what Signature is returning.")
    for reg, payload in raw_responses.items():
        with st.expander(f"Raw JSON output for {reg}"):
            st.json(payload)