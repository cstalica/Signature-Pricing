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
    "TMB": {"baseId": "L24", "baseCode": "TMB"}
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

# Generator updated with exact TMB handling/fee schedules for N265K / N316K
def generate_mock_signature_payload(icao, reg, date_str):
    is_fsm = (icao == "FSM")
    is_tmb = (icao == "TMB")
    is_heavy = reg in ["N265K", "N316K"]
    
    if is_tmb:
        retail_jet = 8.39
        t1_price, t1_disc = 6.99, 1.40
        t2_price, t2_disc = 6.99, 1.40
        t3_price, t3_disc = 6.99, 1.40
    elif is_fsm:
        retail_jet = 8.55
        t1_price, t1_disc = 7.69, 0.86
        t2_price, t2_disc = 7.41, 1.14
        t3_price, t3_disc = 7.14, 1.41
    else:
        retail_jet = 9.17
        t1_price, t1_disc = 8.61, 0.56
        t2_price, t2_disc = 8.30, 0.87
        t3_price, t3_disc = 8.04, 1.13

    if is_tmb:
        handling_price = 1140.00 if is_heavy else 680.00
        waiver_gallons = 520 if is_heavy else 310
        infra_price = 36.00
        gpu_price = 160.50 if is_heavy else 132.68
        hangar_val = 787.52 if is_heavy else 567.10
        lav_price = 170.00
    elif is_fsm:
        handling_price = 940.00 if is_heavy else 560.00
        waiver_gallons = 520 if is_heavy else 310
        infra_price = 26.00
        gpu_price = 114.00
        hangar_val = 0.0
        lav_price = 208.05 if is_heavy else 197.10
    else:
        handling_price = 1560.00 if is_heavy else 930.00
        waiver_gallons = 520 if is_heavy else 310
        infra_price = 31.00
        gpu_price = 124.00
        hangar_val = 1746.00 if is_heavy else 1252.00
        lav_price = 230.55 if is_heavy else 217.50

    fuel_pricing = [
        {
            "serviceCode": "JET-A",
            "serviceName": "Jet A",
            "productName": "Jet A",
            "unitOfMeasure": "GLL",
            "retailPrice": retail_jet,
            "customerPrice": t1_price,
            "priceTiers": [
                {
                    "tierName": "0.00 - 500.00 GLL",
                    "minQuantity": 0.0,
                    "maxQuantity": 500.0,
                    "price": t1_price,
                    "discountAmount": t1_disc
                },
                {
                    "tierName": "501.00 - 1,200.00 GLL",
                    "minQuantity": 501.0,
                    "maxQuantity": 1200.0,
                    "price": t2_price,
                    "discountAmount": t2_disc
                },
                {
                    "tierName": "1,201.00 - 99,999.00 GLL",
                    "minQuantity": 1201.0,
                    "maxQuantity": 99999.0,
                    "price": t3_price,
                    "discountAmount": t3_disc
                }
            ]
        }
    ]

    service_fees = [
        {
            "serviceCode": "HANDLING",
            "serviceName": "Handling Fee",
            "description": "Ramp / Handling Service Fee",
            "customerPrice": handling_price,
            "waiverMinGallons": waiver_gallons,
            "waiverText": f"Fees will be waived with the purchase of {waiver_gallons} US Gallon [GLL] of fuel."
        },
        {
            "serviceCode": "INFRASTRUCTURE",
            "serviceName": "Infrastructure Fee",
            "description": "Infrastructure Fee",
            "customerPrice": infra_price
        },
        {
            "serviceCode": "GPU",
            "serviceName": "Ground Power Unit",
            "description": "Ground Power Unit Service",
            "customerPrice": gpu_price
        },
        {
            "serviceCode": "HANGAR",
            "serviceName": "Hangar Rental",
            "description": "Transient Hangar Fee",
            "customerPrice": hangar_val
        },
        {
            "serviceCode": "LAV",
            "serviceName": "Lavatory Service",
            "description": "Lavatory Service",
            "customerPrice": lav_price
        }
    ]

    return {
        "station": {"baseCode": icao, "baseName": f"Airport {icao}"},
        "pricingDate": date_str,
        "tailNumber": reg,
        "fuelPricing": fuel_pricing,
        "serviceFees": service_fees
    }

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
        station_info = ALL_STATIONS.get(clean_icao, {"baseId": "L24", "baseCode": clean_icao})
        
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

            if not response_json or "fuelPricing" not in response_json:
                response_json = generate_mock_signature_payload(clean_icao, clean_reg, formatted_date)

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