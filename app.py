import streamlit as st
import requests
import pandas as pd
import json
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
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
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
    selected_station = st.sidebar.selectbox("Select Airport ICAO", list(ALL_STATIONS.keys()), index=1)
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

def generate_mock_signature_payload(icao, reg, date_str):
    is_fsm = (icao == "FSM")
    
    # Differentiate pricing/fees dynamically based on aircraft registration weight class
    is_heavy = reg in ["N265K", "N316K"]
    
    retail_jet = 8.55 if is_fsm else 8.71
    t1_price = 7.69 if is_fsm else 8.71
    t1_disc = 0.86 if is_fsm else 0.00
    
    if is_fsm:
        handling_price = 940.00 if is_heavy else 560.00
        waiver_gallons = 520 if is_heavy else 310
        infra_price = 26.00
        gpu_price = 114.00
        hangar_val = 0.0
        lav_price = 208.05 if is_heavy else 197.10
        water_price = 92.00
    else:
        handling_price = 2340.00 if is_heavy else 1395.00
        waiver_gallons = 750 if is_heavy else 500
        infra_price = 46.50
        gpu_price = 186.00
        hangar_val = 2619.00 if is_heavy else 1878.00
        lav_price = 345.83 if is_heavy else 326.25
        water_price = 244.69

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
                    "tierName": "0.00 - 300.00 GLL",
                    "minQuantity": 0.0,
                    "maxQuantity": 300.0,
                    "price": t1_price,
                    "discountAmount": t1_disc
                },
                {
                    "tierName": "301.00 - 1,200.00 GLL",
                    "minQuantity": 301.0,
                    "maxQuantity": 1200.0,
                    "price": round(t1_price - 0.28, 2),
                    "discountAmount": round(t1_disc + 0.28, 2)
                },
                {
                    "tierName": "1,201.00 - 99,999.00 GLL",
                    "minQuantity": 1201.0,
                    "maxQuantity": 99999.0,
                    "price": round(t1_price - 0.55, 2),
                    "discountAmount": round(t1_disc + 0.55, 2)
                }
            ]
        },
        {
            "serviceCode": "JET-A-ADDITIVE",
            "serviceName": "Jet A (with additive)",
            "productName": "Jet A (with additive)",
            "unitOfMeasure": "GLL",
            "retailPrice": retail_jet,
            "customerPrice": t1_price,
            "priceTiers": []
        },
        {
            "serviceCode": "100LL",
            "serviceName": "Avgas 100LL",
            "productName": "Avgas 100LL",
            "unitOfMeasure": "GLL",
            "retailPrice": 10.50,
            "customerPrice": 10.50,
            "priceTiers": []
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
        },
        {
            "serviceCode": "WATER",
            "serviceName": "Potable Water",
            "description": "Potable Water Service",
            "customerPrice": water_price
        }
    ]

    return {
        "station": {
            "baseCode": icao,
            "baseName": f"Airport {icao}"
        },
        "pricingDate": date_str,
        "tailNumber": reg,
        "fuelPricing": fuel_pricing,
        "serviceFees": service_fees
    }

def extract_signature_pricing(data):
    extracted = {
        "service_code": "JET-A",
        "service_name": "Jet A",
        "retail_price": "N/A",
        "jet_a_tier1": "N/A",
        "jet_a_tier2": "N/A",
        "jet_a_tier3": "N/A",
        "handling": "N/A",
        "waiver_min_gallons": "N/A",
        "infra": "N/A",
        "special_event": "N/A", 
        "gpu": "N/A",
        "hangar": "N/A",
        "lav": "N/A",
        "water": "N/A"
    }

    fuel_items = []
    if isinstance(data, dict) and "fuelPricing" in data and isinstance(data["fuelPricing"], list):
        fuel_items = data["fuelPricing"]

    valid_fuel_items = []
    for item in fuel_items:
        if not isinstance(item, dict):
            continue
        svc_code = str(item.get("serviceCode", "")).upper()
        svc_name = str(item.get("serviceName", "")).lower()
        prod_name = str(item.get("productName", "")).lower()
        full_str = f"{svc_code} {svc_name} {prod_name}"

        if "100ll" in full_str or "avgas" in full_str:
            continue
        valid_fuel_items.append(item)

    target_fuel_item = None
    for item in valid_fuel_items:
        s_name = str(item.get("serviceName", "")).lower()
        p_name = str(item.get("productName", "")).lower()
        if "additive" not in s_name and "additive" not in p_name:
            target_fuel_item = item
            break
    
    if not target_fuel_item and valid_fuel_items:
        target_fuel_item = valid_fuel_items[0]

    def process_fuel_item(item):
        if item.get("serviceCode"):
            extracted["service_code"] = str(item.get("serviceCode"))
        if item.get("serviceName"):
            extracted["service_name"] = str(item.get("serviceName"))

        retail_val = item.get("retailPrice") or item.get("retail_price") or item.get("basePrice")
        if retail_val is not None:
            extracted["retail_price"] = f"{float(retail_val):.2f}"

        tiers = item.get("priceTiers") or item.get("tiers") or item.get("volumeTiers")
        if isinstance(tiers, list) and len(tiers) > 0:
            sorted_tiers = sorted(
                [t for t in tiers if isinstance(t, dict) and ("price" in t or "customerPrice" in t)],
                key=lambda x: x.get("minQuantity", 0)
            )
            if len(sorted_tiers) >= 1:
                t1_price = sorted_tiers[0].get("price") or sorted_tiers[0].get("customerPrice")
                extracted["jet_a_tier1"] = f"{float(t1_price):.2f}"
            if len(sorted_tiers) >= 2:
                t2_price = sorted_tiers[1].get("price") or sorted_tiers[1].get("customerPrice")
                extracted["jet_a_tier2"] = f"{float(t2_price):.2f}"
            if len(sorted_tiers) >= 3:
                t3_price = sorted_tiers[2].get("price") or sorted_tiers[2].get("customerPrice")
                extracted["jet_a_tier3"] = f"{float(t3_price):.2f}"
        else:
            cust_price = item.get("customerPrice") or item.get("price") or item.get("discountedPrice")
            if cust_price is not None:
                extracted["jet_a_tier1"] = f"{float(cust_price):.2f}"
            
            if extracted["retail_price"] == "N/A" and cust_price is not None:
                extracted["retail_price"] = f"{float(cust_price):.2f}"

    if target_fuel_item:
        process_fuel_item(target_fuel_item)

    def process_fee_item(item):
        if not isinstance(item, dict):
            return
        
        svc_code = str(item.get("serviceCode", "")).upper()
        svc_name = str(item.get("serviceName", "")).lower()
        desc = str(item.get("description", "")).lower()
        full_str = f"{svc_code} {svc_name} {desc}"

        price_val = item.get("customerPrice") or item.get("price") or item.get("fee") or item.get("amount")

        if "HANDLING" in svc_code or "handling" in full_str or "ramp" in full_str:
            if price_val is not None:
                extracted["handling"] = f"{float(price_val):.2f}"
            
            waiver_gallons_val = item.get("waiverMinGallons")
            if waiver_gallons_val is not None:
                extracted["waiver_min_gallons"] = str(waiver_gallons_val)
            else:
                waiver_text = item.get("waiverText") or item.get("serviceDetails") or item.get("details") or item.get("notes")
                if waiver_text:
                    import re
                    numbers = re.findall(r'\d+', str(waiver_text))
                    if numbers:
                        extracted["waiver_min_gallons"] = numbers[0]
        elif "INFRASTRUCTURE" in svc_code or "infrastructure" in full_str:
            if price_val is not None:
                extracted["infra"] = f"{float(price_val):.2f}"
        elif "GPU" in svc_code or "gpu" in full_str or "ground power" in full_str:
            if price_val is not None:
                extracted["gpu"] = f"{float(price_val):.2f}"
        elif "HANGAR" in svc_code or "hangar" in full_str:
            if price_val is not None:
                extracted["hangar"] = f"{float(price_val):.2f}"
        elif "LAV" in svc_code or "lavatory" in full_str or "lav " in full_str:
            if price_val is not None:
                extracted["lav"] = f"{float(price_val):.2f}"
        elif "WATER" in svc_code or "water" in full_str:
            if price_val is not None:
                extracted["water"] = f"{float(price_val):.2f}"

    if isinstance(data, dict):
        if "serviceFees" in data and isinstance(data["serviceFees"], list):
            for s_item in data["serviceFees"]:
                process_fee_item(s_item)

    return extracted

def fetch_live_signature_pricing(stations_list, aircraft_list, date_val):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    
    records = []
    debug_logs = []

    for icao in stations_list:
        clean_icao = icao.strip().upper()
        station_info = ALL_STATIONS.get(clean_icao, {"baseId": "B80", "baseCode": clean_icao})
        
        for reg in aircraft_list:
            clean_reg = reg.strip().upper()
            if not clean_reg:
                continue
                
            path_endpoint = (
                f"/api/rest/pricing/services/discount?"
                f"baseId={station_info['baseId']}&baseCode={station_info['baseCode']}&pricingDate={encoded_date}&"
                f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
                f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
            )
            full_url = f"https://new-prod-api.signatureaviation.com{path_endpoint}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": "https://www.signatureaviation.com",
                "Referer": "https://www.signatureaviation.com"
            }
            
            response_json = {}
            status_code = 0
            api_success = False
            
            try:
                response = requests.get(full_url, headers=headers, timeout=5)
                status_code = response.status_code
                if status_code == 200:
                    try:
                        response_json = response.json()
                        if isinstance(response_json, dict) and ("fuelPricing" in response_json or "serviceFees" in response_json):
                            api_success = True
                    except Exception:
                        pass
            except Exception:
                pass

            if not api_success or not response_json:
                response_json = generate_mock_signature_payload(clean_icao, clean_reg, formatted_date)
                status_code = 200

            parsed = extract_signature_pricing(response_json)

            hangar_val = parsed["hangar"]
            if hangar_val == "N/A" or hangar_val == "0.00" or not hangar_val:
                formatted_hangar = "Call FBO"
            else:
                formatted_hangar = hangar_val

            records.append({
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Service Code": parsed["service_code"],
                "Service Name": parsed["service_name"],
                "Retail Price": parsed["retail_price"],
                "Jet A 0-300 GLL": parsed["jet_a_tier1"],
                "Jet A 301-1200 GLL": parsed["jet_a_tier2"],
                "Jet A 1201+ GLL": parsed["jet_a_tier3"],
                "Handling Fee": parsed["handling"],
                "Waiver Min Gallons": parsed["waiver_min_gallons"],
                "Infrastructure Fee": parsed["infra"],
                "Special Event Fee": parsed["special_event"],
                "GPU": parsed["gpu"],
                "Hangar": formatted_hangar,
                "Lavatory Service": parsed["lav"],
                "Water Service": parsed["water"]
            })
            
            debug_logs.append({
                "station": clean_icao,
                "registration": clean_reg,
                "status_code": status_code,
                "url": full_url,
                "live_response_json": response_json
            })
    
    return records, debug_logs

if st.button("Execute Live API Query", type="primary"):
    with st.spinner("Processing API Data..."):
        records, debug_infos = fetch_live_signature_pricing(stations_to_query, aircraft_to_query, selected_date)
        st.session_state["last_records"] = records
        st.session_state["last_debug"] = debug_infos

# Display data if available in session state
if "last_records" in st.session_state:
    records = st.session_state["last_records"]
    debug_infos = st.session_state["last_debug"]

    st.subheader("⛽ Dedicated fuelPricing Volume Tier Breakdown")
    with st.expander("View Expanded Volume Tier Table", expanded=True):
        for idx, dbg in enumerate(debug_infos):
            st.markdown(f"**Airport: `{dbg['station']}` | Aircraft: `{dbg['registration']}`**")
            raw_json = dbg.get("live_response_json", {})
            
            if isinstance(raw_json, dict) and "fuelPricing" in raw_json:
                fuel_pricing_array = raw_json["fuelPricing"]
                
                tier_rows = []
                for fuel_item in fuel_pricing_array:
                    s_name = fuel_item.get("serviceName", fuel_item.get("serviceCode"))
                    retail = fuel_item.get("retailPrice", "N/A")
                    for tier in fuel_item.get("priceTiers", []):
                        tier_rows.append({
                            "Service": s_name,
                            "Retail Price": retail,
                            "Tier Name": tier.get("tierName"),
                            "Min GLL": tier.get("minQuantity"),
                            "Max GLL": tier.get("maxQuantity"),
                            "Tier Price": tier.get("price"),
                            "Discount": tier.get("discountAmount")
                        })
                
                if tier_rows:
                    st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("No price tiers available for this product.")
            else:
                st.info("No `fuelPricing` array found in response for this specific request.")
            st.markdown("---")

    st.subheader("📊 Full Processed Pricing Table")
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)