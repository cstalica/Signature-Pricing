import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fee Tracker",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live FBO Service Fees Inspector")
st.markdown("Extracts and displays live handling, infrastructure, and auxiliary service fees using verified station base IDs.")

# Stations with explicit internal baseIds and baseCode as the last 3 letters
ALL_STATIONS = {
    "LGZA": {"baseId": "ZTH", "baseCode": "GZA"},
    "CYYZ": {"baseId": "YYZ", "baseCode": "YYZ"},
    "CYYC": {"baseId": "YYC", "baseCode": "YYC"},
    "CYVR": {"baseId": "YVR", "baseCode": "YVR"},
    "CYUL": {"baseId": "YUL", "baseCode": "YUL"},
    "MPTO": {"baseId": "Y47", "baseCode": "PTO"},
    "KVNY": {"baseId": "VNE", "baseCode": "VNY"},
    "SBVT": {"baseId": "VIX", "baseCode": "BVT"},
    "SBKP": {"baseId": "VCP", "baseCode": "BKP"},
    "KBNA": {"baseId": "V52", "baseCode": "BNA"},
    "KMSP": {"baseId": "V51", "baseCode": "MSP"},
    "KMKE": {"baseId": "V50", "baseCode": "MKE"},
    "KDSM": {"baseId": "V47", "baseCode": "DSM"},
    "KBOS": {"baseId": "V42", "baseCode": "BOS"},
    "PANC": {"baseId": "V40", "baseCode": "ANC"},
    "SBSV": {"baseId": "SSA", "baseCode": "BSV"},
    "EGHI": {"baseId": "SOU", "baseCode": "GHI"},
    "EINN": {"baseId": "SNN", "baseCode": "INN"},
    "LGSM": {"baseId": "SMI", "baseCode": "GSM"},
    "LGTS": {"baseId": "SKG", "baseCode": "GTS"},
    "LSGS": {"baseId": "SIR", "baseCode": "SGS"},
    "SBRJ": {"baseId": "SDU", "baseCode": "BRJ"},
    "LGRP": {"baseId": "RHO", "baseCode": "GRP"},
    "SBRF": {"baseId": "REC", "baseCode": "BRF"},
    "SBPA": {"baseId": "POA", "baseCode": "BPA"},
    "SBBH": {"baseId": "PLU", "baseCode": "BBH"},
    "LGPA": {"baseId": "PAS", "baseCode": "GPA"},
    "KEGE": {"baseId": "P93", "baseCode": "EGE"},
    "KSFO": {"baseId": "P88", "baseCode": "SFO"},
    "KPSP": {"baseId": "P87", "baseCode": "PSP"},
    "KMEM": {"baseId": "P86", "baseCode": "MEM"},
    "KIND": {"baseId": "P85", "baseCode": "IND"},
    "KFLL": {"baseId": "P84", "baseCode": "FLL"},
    "KDEN": {"baseId": "P83", "baseCode": "DEN"},
    "KDAL": {"baseId": "P82", "baseCode": "DAL"},
    "KDAL (P63)": {"baseId": "P63", "baseCode": "DAL"},
    "KBED": {"baseId": "P74", "baseCode": "BED"},
    "KJAX": {"baseId": "P73", "baseCode": "JAX"},
    "KSBA": {"baseId": "P71", "baseCode": "SBA"},
    "KPWK": {"baseId": "P69", "baseCode": "PWK"},
    "KMMU": {"baseId": "P67", "baseCode": "MMU"},
    "KAPA": {"baseId": "P66", "baseCode": "APA"},
    "KPDK": {"baseId": "P65", "baseCode": "PDK"},
    "KTEB": {"baseId": "P62", "baseCode": "TEB"},
    "KDJT": {"baseId": "P61", "baseCode": "DJT"},
    "KHPN": {"baseId": "P60", "baseCode": "HPN"},
    "KHPN (P57)": {"baseId": "P57", "baseCode": "HPN"},
    "KSDL": {"baseId": "P58", "baseCode": "SDL"},
    "KMHT": {"baseId": "P56", "baseCode": "MHT"},
    "KBZN": {"baseId": "P55", "baseCode": "BZN"},
    "KBCT": {"baseId": "P54", "baseCode": "BCT"},
    "KBDL": {"baseId": "P53", "baseCode": "BDL"},
    "KOMA": {"baseId": "P44", "baseCode": "OMA"},
    "KRST": {"baseId": "P39", "baseCode": "RST"},
    "KSTP": {"baseId": "P38", "baseCode": "STP"},
    "KHXD": {"baseId": "P37", "baseCode": "HXD"},
    "KMSY": {"baseId": "P36", "baseCode": "MSY"},
    "KFAT": {"baseId": "P35", "baseCode": "FAT"},
    "KLGB": {"baseId": "P31", "baseCode": "LGB"},
    "KSWF": {"baseId": "P28", "baseCode": "SWF"},
    "KBFM": {"baseId": "P27", "baseCode": "BFM"}
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

def extract_signature_fees(api_response):
    extracted = {
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    data_list = api_response.get("data", []) if isinstance(api_response, dict) else []
    if not data_list:
        return extracted

    station_record = data_list[0] if isinstance(data_list, list) and len(data_list) > 0 else {}

    for s_item in station_record.get("serviceFees", []):
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

def fetch_live_signature_fees(stations_list, aircraft_list, date_val, debug_mode):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []
    
    if debug_mode:
        st.subheader("🔍 Live API Debug Inspector")

    for icao in stations_list:
        clean_icao = icao.strip().upper()
        station_info = ALL_STATIONS.get(clean_icao, {"baseId": clean_icao, "baseCode": clean_icao[-3:]})
        
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*"
            }
            
            response_json = {}
            try:
                res = requests.get(full_url, headers=headers, timeout=5)
                
                if debug_mode:
                    with st.expander(f"API GET Request: {clean_icao} ({station_info['baseId']}) / {clean_reg} (Status: {res.status_code})"):
                        st.text(f"URL: {full_url}")
                        if res.status_code == 200:
                            st.success("Request Successful (200 OK)")
                            try:
                                response_json = res.json()
                                st.json(response_json)
                            except Exception:
                                st.warning("Response was 200 OK but could not parse JSON.")
                                st.text(res.text[:1000])
                        else:
                            st.error(f"Request Failed with Status {res.status_code}")
                            st.code(res.text[:1000])
                else:
                    if res.status_code == 200:
                        response_json = res.json()
            except Exception as e:
                if debug_mode:
                    st.error(f"Network Exception encountered for {clean_icao} / {clean_reg}: {e}")

            parsed = extract_signature_fees(response_json)
            records.append({
                "ICAO": clean_icao,
                "Aircraft Reg": clean_reg,
                "Date": formatted_date,
                "Handling Fee": parsed["handling"],
                "Waiver Min GLL": parsed["waiver_min_gallons"],
                "Infrastructure Fee": parsed["infra"],
                "GPU": parsed["gpu"],
                "Hangar": parsed["hangar"] if parsed["hangar"] != "0.00" else "Call FBO",
                "Lav Service": parsed["lav"]
            })
    return records

# Fetch live records from API
records = fetch_live_signature_fees(stations_to_query, aircraft_to_query, selected_date, enable_debug)

st.subheader("📊 Live FBO Service Fees Table")
df_results = pd.DataFrame(records)

# Display table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Download Button
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Live Fees Table as CSV",
    data=csv_data,
    file_name=f"signature_live_service_fees_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)