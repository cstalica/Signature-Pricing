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

# Create a fingerprint/state signature to automatically detect sidebar option changes
current_selection_state = f"{stations_to_query}-{aircraft_to_query}-{selected_date}"
if "last_selection_state" not in st.session_state:
    st.session_state["last_selection_state"] = current_selection_state
elif st.session_state["last_selection_state"] != current_selection_state:
    st.session_state["last_selection_state"] = current_selection_state
    if "last_records" in st.session_state:
        del st.session_state["last_records"]
    if "last_debug" in st.session_state:
        del st.session_state["last_debug"]
    st.rerun()

def generate_mock_signature_payload(icao, reg, date_str):
    is_fsm = (icao == "FSM")
    is_heavy = reg in ["N265K", "N316K"]
    
    retail_jet = 8.55 if is_fsm else 9.17  # BUF Base Retail Jet A set to 9.17
    
    if is_fsm:
        t1_price = 7.69
        t1_disc = 0.86
        t2_price = 7.41
        t2_disc = 1.14
        t3_price = 7.14
        t3_disc = 1.41
    else:
        # BUF Tiers matched precisely to screenshot data: $8.61, $8.30, $8.04[cite: 2]
        t1_price = 8.61
        t1_disc = 0.56
        t2_price = 8.30
        t2_disc = 0.87
        t3_price = 8.04
        t3_disc = 1.13

    additive_retail = 8.55 if is_fsm else 8.71
    additive_price = 7.69 if is_fsm else 8.71

    if is_fsm:
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
                    "tierName": "0.00 - 500.00 GLL" if not is_fsm else "0.00 - 300.00 GLL",
                    "minQuantity": 0.0,
                    "maxQuantity": 500.0 if not is_fsm else 300.0,
                    "price": t1_price,
                    "discountAmount": t1_disc
                },
                {
                    "tierName": "501.00 - 1,200.00 GLL" if not is_fsm else "301.00 - 1,200.00 GLL",
                    "minQuantity": 501.0 if not is_fsm else 301.0,
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
        },
        {
            "serviceCode": "JET-A-ADDITIVE",
            "serviceName": "Jet A (with additive)",
            "productName": "Jet A (with additive)",
            "unitOfMeasure": "GLL",
            "retailPrice": additive_retail,
            "customerPrice": additive_price,
            "priceTiers": [
                {
                    "tierName": "0.00 - 500.00 GLL" if not is_fsm else "0.00 - 300.00 GLL",
                    "minQuantity": 0.0,
                    "maxQuantity": 500.0 if not is_fsm else 300.0,
                    "price": additive_price,
                    "discountAmount": 0.0
                }
            ]
        },
        {
            "serviceCode": "100LL",
            "serviceName": "Avgas 100LL",
            "productName": "Avgas 100LL",
            "unitOfMeasure": "GLL",
            "retailPrice": 8.60 if not is_fsm else 10.50,
            "customerPrice": 8.60 if not is_fsm else 10.50,
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
        "lav": "N/A"
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

    # Prioritize standard Jet A over Jet A with additive if both are available
    target_fuel_item = None
    for item in valid_fuel_items:
        s_name = str(item.get("serviceName", "")).lower()
        p_name = str(item.get("productName", "")).lower()
        s_code = str(item.get("serviceCode", "")).upper()
        if "additive" not in s_name and "additive" not in p_name and "ADDITIVE" not in s_code:
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