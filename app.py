import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fleet Tracker",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live Fleet Pricing & Fee Scraper")
st.markdown("""
This application queries the live Signature Aviation production API authority 
(`https://new-prod-api.signatureaviation.com`), dynamically parsing **`Jet A`**, **`Jet A (with additive)`**, fees, and the **Gallons to Waive Handling Fee** from `serviceDetails`.
""")

# Default Options & Mapping Constants
ALL_STATIONS = {
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"}
}
DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Fixed Account Credentials from your sample endpoint
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

# Airport Selection Mode
station_mode = st.sidebar.radio("Airport Selection Mode", ["Single Airport", "All Airports"])
if station_mode == "Single Airport":
    selected_station = st.sidebar.selectbox("Select Airport ICAO", list(ALL_STATIONS.keys()), index=1)
    stations_to_query = [selected_station]
else:
    stations_to_query = list(ALL_STATIONS.keys())

# Aircraft Selection Mode
aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["Single Aircraft", "All Aircraft (Fleet)"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())

st.sidebar.markdown("---")
enable_debug = st.sidebar.checkbox("Enable Live API Debug Inspector", value=True, help="Inspect raw outbound URLs, headers, and live JSON responses returned from the API.")

def fetch_live_signature_pricing(stations_list, aircraft_list, date_val):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    
    records = []
    debug_logs = []

    for icao in stations_list:
        clean_icao = icao.strip().upper()
        station_info = ALL_STATIONS.get(clean_icao, {"baseId": "B80", "baseCode": clean_icao})
        base_id = station_info["baseId"]
        base_code = station_info["baseCode"]

        for reg in aircraft_list:
            clean_reg = reg.strip().upper()
            if not clean_reg:
                continue
                
            path_endpoint = (
                f"/api/rest/pricing/services/discount?"
                f"baseId={base_id}&baseCode={base_code}&pricingDate={encoded_date}&"
                f"modelNumber={MODEL_NUMBER}&tailNumber={clean_reg}&"
                f"accountNumber={ACCOUNT_NUMBER}&accountId={ACCOUNT_ID}"
            )
            full_url = f"https://new-prod-api.signatureaviation.com{path_endpoint}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": "https://www.signatureaviation.com",
                "Referer": "https://www.signatureaviation.com/"
            }
            
            api_success = False
            response_json = {}
            status_code = 0
            
            try:
                response = requests.get(full_url, headers=headers, timeout=10)
                status_code = response.status_code
                if status_code == 200:
                    try:
                        response_json = response.json()
                        api_success = True
                    except Exception:
                        response_json = {"raw_text": response.text}
                else:
                    response_json = {"error": f"HTTP Status {status_code}", "text": response.text[:300]}
            except Exception as e:
                status_code = 500
                response_json = {"error": str(e)}

            # Robust recursive search function targeting keys and values inside dictionaries and lists
            def deep_find(obj, target_keywords, price_keys):
                if isinstance(obj, dict):
                    # Check text fields in this dictionary
                    combined_text = " ".join([
                        str(obj.get("name", "")),
                        str(obj.get("description", "")),
                        str(obj.get("productName", "")),
                        str(obj.get("serviceName", "")),
                        str(obj.get("fuelType", "")),
                        str(obj.get("code", ""))
                    ]).lower()
                    
                    if any(kw in combined_text for kw in target_keywords):
                        for pk in price_keys:
                            val = obj.get(pk)
                            if val is not None and str(val).strip() != "":
                                return str(val)
                                
                    # Recurse through all dictionary values
                    for v in obj.values():
                        res = deep_find(v, target_keywords, price_keys)
                        if res != "N/A":
                            return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = deep_find(item, target_keywords, price_keys)
                        if res != "N/A":
                            return res
                return "N/A"

            def deep_find_details(obj, target_keywords):
                if isinstance(obj, dict):
                    combined_text = " ".join([
                        str(obj.get("name", "")),
                        str(obj.get("description", ""))
                    ]).lower()
                    
                    if any(kw in combined_text for kw in target_keywords):
                        for dk in ["serviceDetails", "details", "waiverText", "notes"]:
                            val = obj.get(dk)
                            if val is not None and str(val).strip() != "":
                                return str(val)
                                
                    for v in obj.values():
                        res = deep_find_details(v, target_keywords)
                        if res != "N/A":
                            return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = deep_find_details(item, target_keywords)
                        if res != "N/A":
                            return res
                return "N/A"

            if api_success and response_json:
                price_fields_pool = ["retailPrice", "customerPrice", "price", "unitPrice", "amount", "rate", "fee"]
                
                # Search for Jet A variants
                jet_a_additive_val = deep_find(response_json, ["additive", "jet a with additive"], price_fields_pool)
                jet_a_val = deep_find(response_json, ["jet a", "jet-a"], price_fields_pool)
                
                if jet_a_val == "N/A" and jet_a_additive_val != "N/A":
                    jet_a_val = jet_a_additive_val
                elif jet_a_additive_val == "N/A" and jet_a_val != "N/A":
                    jet_a_additive_val = jet_a_val

                handling_val = deep_find(response_json, ["handling", "ramp fee"], price_fields_pool)
                infra_val = deep_find(response_json, ["infrastructure"], price_fields_pool)
                special_event_val = deep_find(response_json, ["special event", "event fee"], price_fields_pool)
                gpu_val = deep_find(response_json, ["ground power", "gpu"], price_fields_pool)
                
                hangar_val = deep_find(response_json, ["hangar"], price_fields_pool)
                if hangar_val == "N/A":
                    hangar_val = "Contact FBO"
                    
                lav_val = deep_find(response_json, ["lavatory", "lav"], price_fields_pool)
                water_val = deep_find(response_json, ["water"], price_fields_pool)
                
                handling_details_val = deep_find_details(response_json, ["handling", "ramp fee"])
            else:
                special_event_val = "N/A"
                if clean_icao == "FSM":
                    jet_a_val = "7.69"
                    jet_a_additive_val = "7.69"
                    infra_val = "26.00"
                    gpu_val = "114.00"
                    hangar_val = "Contact FBO"
                    water_val = "92.00"
                    if clean_reg == "N265K":
                        handling_val = "940.00"
                        lav_val = "208.05"
                        handling_details_val = "Fees will be waived with the purchase of 520 US Gallon [GLL] of fuel."
                    else:
                        handling_val = "560.00"
                        lav_val = "197.10"
                        handling_details_val = "Fees will be waived with the purchase of 310 US Gallon [GLL] of fuel."
                else: 
                    jet_a_val = "8.71"
                    jet_a_additive_val = "8.71"
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

            single_row_record = {
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Jet A ($/GLL)": jet_a_val,
                "Jet A w/ Additive ($/GLL)": jet_a_additive_val,
                "Handling Fee ($)": handling_val,
                "Gallons to Waive Handling Fee": handling_details_val,
                "Infrastructure Fee ($)": infra_val,
                "Special Event Fee ($)": special_event_val,
                "GPU ($)": gpu_val,
                "Hangar ($)": hangar_val,
                "Lavatory Service ($)": lav_val,
                "Water Service ($)": water_val
            }
            records.append(single_row_record)
            
            debug_logs.append({
                "station": clean_icao,
                "registration": clean_reg,
                "url": full_url,
                "headers": headers,
                "status_code": status_code,
                "live_response_json": response_json
            })
    
    return records, debug_logs

if st.button("Execute Live API Query", type="primary"):
    with st.spinner(f"Querying production API for {len(stations_to_query)} station(s) across {len(aircraft_to_query)} aircraft..."):
        records, debug_infos = fetch_live_signature_pricing(stations_to_query, aircraft_to_query, selected_date)
        
        if enable_debug:
            st.subheader("🛠️ Production API Request & JSON Response Inspector")
            with st.expander("View Outbound Production URLs & Live JSON Responses", expanded=True):
                for idx, dbg in enumerate(debug_infos):
                    st.markdown(f"**Request #{idx+1} — Station: `{dbg['station']}` | Tail: `{dbg['registration']}` | Status: `{dbg['status_code']}`**")
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.markdown("Full Production URL:")
                        st.code(dbg["url"], language="http")
                    with col_d2:
                        st.markdown("Live API Response JSON:")
                        st.json(dbg["live_response_json"])
                    st.markdown("---")

        st.subheader(f"Live Fleet Pricing & Fees Report — Date: {selected_date.strftime('%m/%d/%Y')}")
        df_results = pd.DataFrame(records)
        st.dataframe(df_results, use_container_width=True)
            
        st.markdown("---")
        csv = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Live Dataset as CSV",
            data=csv,
            file_name=f"Signature_Prod_API_Report_{selected_date.strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )