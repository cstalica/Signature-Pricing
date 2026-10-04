import streamlit as st
import requests
import pandas as pd
import json
import re
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fleet Tracker",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ Signature Aviation — Brute-Force Live API Scraper")
st.markdown("This version uses an aggressive brute-force crawler to scan every nested level of the JSON for any valid float associated with fuel and fees.")

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
            
            try:
                response = requests.get(full_url, headers=headers, timeout=10)
                status_code = response.status_code
                if status_code == 200:
                    try:
                        response_json = response.json()
                    except Exception:
                        response_json = {"raw_text": response.text[:500] + "... (truncated)"}
                else:
                    response_json = {"error": f"HTTP {status_code}"}
            except Exception as e:
                response_json = {"error": str(e)}

            # BRUTE FORCE PARSER
            def brute_force_extract(data):
                extracted = {
                    "jet_a": "N/A", "jet_a_additive": "N/A", 
                    "handling": "N/A", "handling_details": "N/A",
                    "infra": "N/A", "special_event": "N/A", 
                    "gpu": "N/A", "hangar": "N/A", "lav": "N/A", "water": "N/A"
                }

                # Recursively extract every single number inside a given dictionary
                def get_lowest_price(node_dict):
                    nums = []
                    def _extract(n):
                        if isinstance(n, dict):
                            for k, v in n.items():
                                if isinstance(v, (int, float)):
                                    nums.append(float(v))
                                elif isinstance(v, str) and re.match(r"^\d+\.\d{2}$", v):
                                    nums.append(float(v))
                                else:
                                    _extract(v)
                        elif isinstance(n, list):
                            for i in n:
                                _extract(i)
                    _extract(node_dict)
                    
                    # Filter for realistic prices (ignore tiny decimals or massive IDs)
                    valid_prices = [p for p in nums if 0.1 < p < 10000]
                    return f"{min(valid_prices):.2f}" if valid_prices else "N/A"

                def traverse(node):
                    if isinstance(node, dict):
                        # Combine all string values in this dictionary level to identify what it is
                        dict_strings = " ".join([str(v).lower() for k, v in node.items() if isinstance(v, str)])
                        
                        # Only target dictionaries that seem to describe a product
                        if any(k in str(node.keys()).lower() for k in ["name", "desc", "product", "type", "service"]):
                            
                            if "additive" in dict_strings or "jet a (with" in dict_strings:
                                extracted["jet_a_additive"] = get_lowest_price(node)
                            elif "jet a" in dict_strings or "jeta" in dict_strings:
                                extracted["jet_a"] = get_lowest_price(node)
                            elif "handling" in dict_strings or "ramp" in dict_strings:
                                extracted["handling"] = get_lowest_price(node)
                                for dk in ["serviceDetails", "details", "waiverText", "notes"]:
                                    if node.get(dk):
                                        extracted["handling_details"] = str(node.get(dk))
                            elif "infrastructure" in dict_strings:
                                extracted["infra"] = get_lowest_price(node)
                            elif "gpu" in dict_strings or "ground power" in dict_strings:
                                extracted["gpu"] = get_lowest_price(node)
                            elif "hangar" in dict_strings:
                                extracted["hangar"] = get_lowest_price(node)
                            elif "lavatory" in dict_strings or "lav " in dict_strings:
                                extracted["lav"] = get_lowest_price(node)
                            elif "water" in dict_strings:
                                extracted["water"] = get_lowest_price(node)

                        for val in node.values():
                            traverse(val)
                    elif isinstance(node, list):
                        for item in node:
                            traverse(item)

                traverse(data)
                
                # Cross-fill Jet A if one was found but not the other
                if extracted["jet_a"] != "N/A" and extracted["jet_a_additive"] == "N/A":
                    extracted["jet_a_additive"] = extracted["jet_a"]
                elif extracted["jet_a_additive"] != "N/A" and extracted["jet_a"] == "N/A":
                    extracted["jet_a"] = extracted["jet_a_additive"]
                    
                return extracted

            parsed = brute_force_extract(response_json)

            records.append({
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Jet A ($/GLL)": parsed["jet_a"],
                "Jet A w/ Additive ($/GLL)": parsed["jet_a_additive"],
                "Handling Fee ($)": parsed["handling"],
                "Gallons to Waive Handling Fee": parsed["handling_details"],
                "Infrastructure Fee ($)": parsed["infra"],
                "Special Event Fee ($)": parsed["special_event"],
                "GPU ($)": parsed["gpu"],
                "Hangar ($)": parsed["hangar"] if parsed["hangar"] != "N/A" else "Contact FBO",
                "Lavatory Service ($)": parsed["lav"],
                "Water Service ($)": parsed["water"]
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
    with st.spinner("Executing Brute-Force crawler on live API..."):
        records, debug_infos = fetch_live_signature_pricing(stations_to_query, aircraft_to_query, selected_date)
        
        if enable_debug:
            st.subheader("🛠️ Debug Inspector")
            with st.expander("View Outbound Production URLs & Live JSON Responses", expanded=True):
                for idx, dbg in enumerate(debug_infos):
                    st.markdown(f"**Request #{idx+1} — {dbg['station']} | {dbg['registration']} | HTTP {dbg['status_code']}**")
                    st.json(dbg["live_response_json"])
                    st.markdown("---")

        st.dataframe(pd.DataFrame(records), use_container_width=True)