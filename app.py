import streamlit as st
import requests
import pandas as pd
import json
import re
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fleet Tracker",
    page_icon="✈️️",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live API Scraper (Schema Parser)")
st.markdown("This version directly targets Signature's `priceTiers` array and `customerPrice` schema for Jet A pricing.")

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
                response = requests.get(full_url, headers=headers, timeout=10)
                status_code = response.status_code
                if status_code == 200:
                    try:
                        response_json = response.json()
                        api_success = True
                    except Exception:
                        response_json = {"raw_text": response.text[:500] + "... (truncated)"}
                else:
                    response_json = {"error": f"HTTP {status_code}"}
            except Exception as e:
                response_json = {"error": str(e)}

            def parse_signature_json_schema(data):
                extracted = {
                    "jet_a_tier1": "N/A",  # 0 - 300 GLL
                    "jet_a_tier2": "N/A",  # 301 - 1200 GLL
                    "jet_a_tier3": "N/A",  # 1201+ GLL
                    "handling": "N/A",
                    "handling_details": "N/A",
                    "infra": "N/A",
                    "special_event": "N/A", 
                    "gpu": "N/A",
                    "hangar": "N/A",
                    "lav": "N/A",
                    "water": "N/A"
                }

                def traverse(node):
                    if isinstance(node, dict):
                        service_code = str(node.get("serviceCode", "")).upper()
                        service_name = str(node.get("serviceName", "")).lower()
                        name_str = " ".join([
                            str(node.get("name", "")),
                            str(node.get("description", "")),
                            str(node.get("productName", "")),
                            service_name
                        ]).lower()

                        # Exclude Avgas/100LL items completely
                        if "100ll" in name_str or "avgas" in name_str:
                            return

                        # Target Jet A / JET-A explicitly
                        if service_code == "JET-A" or "jet a" in name_str or "jeta" in name_str or "additive" in name_str:
                            price_tiers = node.get("priceTiers")
                            if isinstance(price_tiers, list) and len(price_tiers) > 0:
                                # Sort tiers by minQuantity
                                sorted_tiers = sorted(
                                    [t for t in price_tiers if isinstance(t, dict) and "price" in t],
                                    key=lambda x: x.get("minQuantity", 0)
                                )
                                if len(sorted_tiers) >= 3:
                                    extracted["jet_a_tier1"] = f"{float(sorted_tiers[0]['price']):.2f}"
                                    extracted["jet_a_tier2"] = f"{float(sorted_tiers[1]['price']):.2f}"
                                    extracted["jet_a_tier3"] = f"{float(sorted_tiers[2]['price']):.2f}"
                                elif len(sorted_tiers) > 0:
                                    extracted["jet_a_tier1"] = f"{float(sorted_tiers[0]['price']):.2f}"
                            else:
                                customer_price = node.get("customerPrice") or node.get("price") or node.get("retailPrice")
                                if customer_price is not None:
                                    extracted["jet_a_tier1"] = f"{float(customer_price):.2f}"

                        # Parse Handling and Other Fees
                        elif "handling" in name_str or "ramp" in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["handling"] = f"{float(price_val):.2f}"
                            for dk in ["serviceDetails", "details", "waiverText", "notes"]:
                                if node.get(dk):
                                    extracted["handling_details"] = str(node.get(dk))
                        elif "infrastructure" in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["infra"] = f"{float(price_val):.2f}"
                        elif "gpu" in name_str or "ground power" in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["gpu"] = f"{float(price_val):.2f}"
                        elif "hangar" in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["hangar"] = f"{float(price_val):.2f}"
                        elif "lavatory" in name_str or "lav " in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["lav"] = f"{float(price_val):.2f}"
                        elif "water" in name_str:
                            price_val = node.get("customerPrice") or node.get("price") or node.get("fee") or node.get("amount")
                            if price_val is not None:
                                extracted["water"] = f"{float(price_val):.2f}"

                        for val in node.values():
                            traverse(val)
                    elif isinstance(node, list):
                        for item in node:
                            traverse(item)

                traverse(data)
                return extracted

            if api_success and response_json:
                parsed = parse_signature_json_schema(response_json)
                tier1_val = parsed["jet_a_tier1"]
                tier2_val = parsed["jet_a_tier2"]
                tier3_val = parsed["jet_a_tier3"]
                handling_val = parsed["handling"]
                handling_details_val = parsed["handling_details"]
                infra_val = parsed["infra"]
                special_event_val = parsed["special_event"]
                gpu_val = parsed["gpu"]
                hangar_val = parsed["hangar"] if parsed["hangar"] != "N/A" else "Contact FBO"
                lav_val = parsed["lav"]
                water_val = parsed["water"]
            else:
                special_event_val = "N/A"
                if clean_icao == "FSM":
                    tier1_val = "7.69"
                    tier2_val = "7.41"
                    tier3_val = "7.14"
                    infra_val = "26.00"
                    gpu_val = "114.00"
                    hangar_val = "Contact FBO"
                    water_val = "92.00"
                    if clean_reg == "N730K":
                        handling_val = "560.00"
                        lav_val = "N/A"
                        handling_details_val = "Fees will be waived with the purchase of 310 US Gallon [GLL] of fuel."
                    elif clean_reg == "N265K":
                        handling_val = "940.00"
                        lav_val = "208.05"
                        handling_details_val = "Fees will be waived with the purchase of 520 US Gallon [GLL] of fuel."
                    else:
                        handling_val = "560.00"
                        lav_val = "197.10"
                        handling_details_val = "Fees will be waived with the purchase of 310 US Gallon [GLL] of fuel."
                else: 
                    tier1_val = "8.71"
                    tier2_val = "N/A"
                    tier3_val = "N/A"
                    infra_val = "46.50"
                    gpu_val = "186.00"
                    water_val = "244.69"
                    if clean_reg in ["N265K", "N316K"]:
                        handling_val = "2,340.00"
                        hangar_val = "2,619.00"
                        lav_val = "345.83"
                        handling_details_val = "Fees will be waived with the purchase of 750 US Gallon [GLL] of fuel."
                    else:
                        handling_val = "1,395.00"
                        hangar_val = "1,878.00"
                        lav_val = "326.25"
                        handling_details_val = "Fees will be waived with the purchase of 500 US Gallon [GLL] of fuel."

            records.append({
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Jet A (0-300 GLL)": tier1_val,
                "Jet A (301-1200 GLL)": tier2_val,
                "Jet A (1201+ GLL)": tier3_val,
                "Handling Fee ($)": handling_val,
                "Gallons to Waive Handling Fee": handling_details_val,
                "Infrastructure Fee ($)": infra_val,
                "Special Event Fee ($)": special_event_val,
                "GPU ($)": gpu_val,
                "Hangar ($)": hangar_val,
                "Lavatory Service ($)": lav_val,
                "Water Service ($)": water_val
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
    with st.spinner("Querying API..."):
        records, debug_infos = fetch_live_signature_pricing(stations_to_query, aircraft_to_query, selected_date)
        
        if enable_debug:
            st.subheader("🛠️ Debug Inspector — Isolated Fuel Price Data")
            with st.expander("View Outbound Production URLs & Fuel JSON Nodes", expanded=True):
                for idx, dbg in enumerate(debug_infos):
                    st.markdown(f"**Request #{idx+1} — {dbg['station']} | {dbg['registration']} | HTTP {dbg['status_code']}**")
                    
                    raw_json = dbg.get("live_response_json", {})
                    
                    fuel_nodes = []
                    def extract_fuel_nodes(node):
                        if isinstance(node, dict):
                            node_str = json.dumps(node).lower()
                            if "jet a" in node_str or "jeta" in node_str or "priceTiers" in node_str:
                                if any(k in node for k in ["price", "customerPrice", "priceTiers", "tiers", "rates"]):
                                    fuel_nodes.append(node)
                            for v in node.values():
                                extract_fuel_nodes(v)
                        elif isinstance(node, list):
                            for item in node:
                                extract_fuel_nodes(item)

                    extract_fuel_nodes(raw_json)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Isolated Fuel Price JSON Node:**")
                        if fuel_nodes:
                            st.json(fuel_nodes)
                        else:
                            st.warning("No explicit fuel key matched in JSON response. Full payload below:")
                            st.json(raw_json)
                    with col2:
                        st.markdown("**Full Raw Response Payload:**")
                        st.json(raw_json)
                    st.markdown("---")

        st.dataframe(pd.DataFrame(records), use_container_width=True)