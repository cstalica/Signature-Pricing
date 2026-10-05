import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Direct API Inspector",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Direct REST API Pricing Inspector")
st.markdown("Queries Signature Aviation's live pricing REST endpoint directly for aircraft fleets across stations.")

# Station Mapping & Account Details
ALL_STATIONS = {
    "MIA": {"baseId": "L23", "baseCode": "MIA"},
    "OPF": {"baseId": "L26", "baseCode": "OPF"},
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
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
    index=2
)

aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["All Aircraft (Fleet)", "Single Aircraft"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())


def extract_signature_pricing(data):
    """Parses raw Signature REST API JSON payload into structured fuel and fee records."""
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

    if not data or not isinstance(data, (dict, list)):
        return extracted

    # Unpack nested structures if present
    payload = data
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], (dict, list)):
            payload = payload["data"]
    if isinstance(payload, dict):
        if "result" in payload and isinstance(payload["result"], (dict, list)):
            payload = payload["result"]

    fuel_items = []
    service_items = []

    if isinstance(payload, dict):
        fuel_items = payload.get("fuelPricing", payload.get("fuelPrices", []))
        service_items = payload.get("serviceFees", payload.get("services", []))
    elif isinstance(payload, list):
        fuel_items = payload
        service_items = payload

    if not isinstance(fuel_items, list): fuel_items = []
    if not isinstance(service_items, list): service_items = []

    # Parse Jet A Pricing & Tiers
    target_fuel = None
    for item in fuel_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("serviceCode", item.get("code", ""))).upper()
        name = str(item.get("serviceName", item.get("name", ""))).upper()
        if ("JET A" in name or "JET" in code) and "ADDITIVE" not in name and "100LL" not in name and "SAF" not in name:
            target_fuel = item
            break

    if not target_fuel and fuel_items:
        for item in fuel_items:
            if isinstance(item, dict):
                target_fuel = item
                break

    if target_fuel:
        retail = target_fuel.get("retailPrice", target_fuel.get("retail"))
        if retail is not None:
            try:
                extracted["retail_price"] = f"${float(retail):.2f}"
            except (ValueError, TypeError):
                extracted["retail_price"] = str(retail)

        cust_p = target_fuel.get("customerPrice", target_fuel.get("price"))
        if cust_p is not None:
            try:
                extracted["jet_a_tier1"] = f"${float(cust_p):.2f}"
            except (ValueError, TypeError):
                extracted["jet_a_tier1"] = str(cust_p)

        tiers = target_fuel.get("priceTiers", target_fuel.get("tiers", []))
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted(
                [t for t in tiers if isinstance(t, dict)],
                key=lambda x: float(x.get("minQuantity", x.get("minQty", 0)))
            )
            for idx, tier in enumerate(sorted_tiers):
                p = tier.get("price", tier.get("customerPrice"))
                if p is not None:
                    try:
                        val = f"${float(p):.2f}"
                    except (ValueError, TypeError):
                        val = str(p)
                    if idx == 0:
                        extracted["jet_a_tier1"] = val
                    elif idx == 1:
                        extracted["jet_a_tier2"] = val
                    elif idx == 2:
                        extracted["jet_a_tier3"] = val

    # Parse Service Fees
    for s_item in service_items:
        if not isinstance(s_item, dict):
            continue
        code = str(s_item.get("serviceCode", s_item.get("code", ""))).upper()
        name = str(s_item.get("serviceName", s_item.get("name", ""))).upper()
        price = s_item.get("customerPrice", s_item.get("price", s_item.get("amount")))

        if price is not None:
            try:
                val_str = f"${float(price):.2f}"
            except (ValueError, TypeError):
                val_str = str(price)

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


def fetch_signature_pricing_api(icao, aircraft_list, date_val):
    """Executes direct REST API request to Signature Aviation's discount pricing endpoint."""
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    
    station_info = ALL_STATIONS.get(icao, ALL_STATIONS["TMB"])
    
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.signatureaviation.com/",
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
            res = session.get(api_url, headers=headers, timeout=8)
            if res.status_code == 200:
                response_json = res.json()
            else:
                st.warning(f"HTTP {res.status_code} returned for {clean_reg} at {icao}")
        except Exception as e:
            st.error(f"Connection error for {clean_reg}: {e}")

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
        
    return records


# Render App Data
with st.spinner(f"Fetching direct REST API data for {selected_station_icao}..."):
    records = fetch_signature_pricing_api(selected_station_icao, aircraft_to_query, selected_date)

st.subheader(f"📊 Live API Data — {selected_station_icao}")
df_results = pd.DataFrame(records)

# Render Data Table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Export
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download {selected_station_icao} Pricing CSV",
    data=csv_data,
    file_name=f"signature_{selected_station_icao}_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)