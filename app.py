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
show_debug = st.sidebar.checkbox("Enable Raw API Debug Panel", value=False)


def find_key_recursive(data, target_keys):
    """Recursively searches nested dicts/lists for any matching keys."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in [tk.lower() for tk in target_keys]:
                return v
            res = find_key_recursive(v, target_keys)
            if res is not None:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_key_recursive(item, target_keys)
            if res is not None:
                return res
    return None


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
        "jet_a_tier1": "N/A",
        "jet_a_tier2": "N/A",
        "jet_a_tier3": "N/A",
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
        for wrapper in ["data", "result", "payload", "pricingDetail"]:
            if wrapper in root and isinstance(root[wrapper], (dict, list)):
                root = root[wrapper]

    # Gather items list
    items_list = []
    if isinstance(root, list):
        items_list = root
    elif isinstance(root, dict):
        # Collect all list values inside the dictionary
        for k, v in root.items():
            if isinstance(v, list):
                items_list.extend(v)

    # 1. Parse Fuel Pricing
    target_fuel = None
    for item in items_list:
        if not isinstance(item, dict):
            continue
        code = str(item.get("serviceCode", item.get("code", item.get("productCode", "")))).upper()
        name = str(item.get("serviceName", item.get("name", item.get("productName", "")))).upper()
        
        if ("JET" in name or "JET" in code) and "100LL" not in name and "AVGAS" not in name:
            target_fuel = item
            break

    if target_fuel:
        # Retail Price
        retail = extract_price_val(target_fuel, ["retailPrice", "retail", "listPrice", "basePrice", "retailRate"])
        if retail:
            extracted["retail_price"] = retail

        # Customer Price / Tier 1
        cust_p = extract_price_val(target_fuel, ["customerPrice", "price", "netPrice", "discountPrice", "rate", "unitPrice"])
        if cust_p:
            extracted["jet_a_tier1"] = cust_p

        # Tiers
        tiers = target_fuel.get("priceTiers", target_fuel.get("tiers", target_fuel.get("volumeTiers", [])))
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted(
                [t for t in tiers if isinstance(t, dict)],
                key=lambda x: float(x.get("minQuantity", x.get("minQty", x.get("volumeMin", 0))))
            )
            for idx, tier in enumerate(sorted_tiers):
                p_val = extract_price_val(tier, ["price", "customerPrice", "rate", "netPrice"])
                if p_val:
                    if idx == 0:
                        extracted["jet_a_tier1"] = p_val
                    elif idx == 1:
                        extracted["jet_a_tier2"] = p_val
                    elif idx == 2:
                        extracted["jet_a_tier3"] = p_val

    # 2. Parse Service Fees
    for item in items_list:
        if not isinstance(item, dict):
            continue
        code = str(item.get("serviceCode", item.get("code", item.get("productCode", "")))).upper()
        name = str(item.get("serviceName", item.get("name", item.get("productName", "")))).upper()
        
        fee_val = extract_price_val(item, ["customerPrice", "price", "amount", "netPrice", "rate", "feeAmount", "totalPrice"])
        
        if fee_val:
            if any(k in code or k in name for k in ["HANDLING", "RAMP", "FACILITY"]):
                extracted["handling"] = fee_val
                waiver_gal = item.get("waiverMinGallons", item.get("waiverGallons", item.get("minFuelWaiver")))
                if waiver_gal:
                    extracted["waiver_min_gallons"] = f"{waiver_gal} gal"
            elif any(k in code or k in name for k in ["INFRASTRUCTURE", "INFRA", "SECURITY"]):
                extracted["infra"] = fee_val
            elif any(k in code or k in name for k in ["GPU", "GROUND POWER", "POWER"]):
                extracted["gpu"] = fee_val
            elif any(k in code or k in name for k in ["HANGAR", "PARKING"]):
                extracted["hangar"] = fee_val
            elif any(k in code or k in name for k in ["LAV", "LAVATORY"]):
                extracted["lav"] = fee_val

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
                st.warning(f"Station {icao} ({clean_reg}): HTTP {res.status_code}")
        except Exception as e:
            st.error(f"Connection error for {clean_reg} at {icao}: {e}")

        raw_responses[clean_reg] = response_json
        parsed = extract_signature_pricing(response_json)
        
        records.append({
            "ICAO": icao,
            "Aircraft Reg": clean_reg,
            "Date": formatted_date,
            "Retail Jet A": parsed["retail_price"],
            "Jet A Tier 1 (0-500 gal)": parsed["jet_a_tier1"],
            "Jet A Tier 2 (501-1200 gal)": parsed["jet_a_tier2"],
            "Jet A Tier 3 (1201+ gal)": parsed["jet_a_tier3"],
            "Handling Fee": parsed["handling"],
            "Waiver Min Fuel": parsed["waiver_min_gallons"],
            "Infrastructure Fee": parsed["infra"],
            "GPU Fee": parsed["gpu"],
            "Hangar Fee": parsed["hangar"],
            "Lav Service": parsed["lav"]
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