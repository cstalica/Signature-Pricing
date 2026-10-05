import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation Live API & Fee Tracker",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — Live FBO Service Fees Inspector")
st.markdown("Extracts and displays live handling, infrastructure, and auxiliary service fees using verified station base IDs.")

# Filtered (starts with 'K') and alphabetically sorted stations from locations_output.csv
ALL_STATIONS = {
    "KACY": {"baseId": "L27", "baseCode": "ACY"},
    "KAMA": {"baseId": "B82", "baseCode": "AMA"},
    "KAPA (B86)": {"baseId": "B86", "baseCode": "APA"},
    "KAPA (P66)": {"baseId": "P66", "baseCode": "APA"},
    "KATL": {"baseId": "L35", "baseCode": "ATL"},
    "KAUS": {"baseId": "P21", "baseCode": "AUS"},
    "KAVL": {"baseId": "L09", "baseCode": "AVL"},
    "KBCT": {"baseId": "P54", "baseCode": "BCT"},
    "KBDL": {"baseId": "P53", "baseCode": "BDL"},
    "KBED": {"baseId": "P74", "baseCode": "BED"},
    "KBFI": {"baseId": "L20", "baseCode": "BFI"},
    "KBFM": {"baseId": "P27", "baseCode": "BFM"},
    "KBJC": {"baseId": "L54", "baseCode": "BJC"},
    "KBKL": {"baseId": "L07", "baseCode": "BKL"},
    "KBNA": {"baseId": "V52", "baseCode": "BNA"},
    "KBOS": {"baseId": "V42", "baseCode": "BOS"},
    "KBTR": {"baseId": "L52", "baseCode": "BTR"},
    "KBUF": {"baseId": "B85", "baseCode": "BUF"},
    "KBWI": {"baseId": "B09", "baseCode": "BWI"},
    "KBZN": {"baseId": "P55", "baseCode": "BZN"},
    "KCHO": {"baseId": "L48", "baseCode": "CHO"},
    "KCHS": {"baseId": "L16", "baseCode": "CHS"},
    "KCID": {"baseId": "L36", "baseCode": "CID"},
    "KCMH": {"baseId": "L14", "baseCode": "CMH"},
    "KDAL (B84)": {"baseId": "B84", "baseCode": "DAL"},
    "KDAL (L45)": {"baseId": "L45", "baseCode": "DAL"},
    "KDAL (P63)": {"baseId": "P63", "baseCode": "DAL"},
    "KDAL (P82)": {"baseId": "P82", "baseCode": "DAL"},
    "KDCA": {"baseId": "B10", "baseCode": "DCA"},
    "KDEN": {"baseId": "P83", "baseCode": "DEN"},
    "KDJT (K60)": {"baseId": "K60", "baseCode": "DJT"},
    "KDJT (P61)": {"baseId": "P61", "baseCode": "DJT"},
    "KDSM": {"baseId": "V47", "baseCode": "DSM"},
    "KDTW": {"baseId": "P09", "baseCode": "DTW"},
    "KEFD": {"baseId": "L59", "baseCode": "EFD"},
    "KEGE": {"baseId": "P93", "baseCode": "EGE"},
    "KEWR": {"baseId": "B07", "baseCode": "EWR"},
    "KEYW": {"baseId": "L32", "baseCode": "EYW"},
    "KF45": {"baseId": "L31", "baseCode": "F45"},
    "KFAT": {"baseId": "P35", "baseCode": "FAT"},
    "KFAY": {"baseId": "L39", "baseCode": "FAY"},
    "KFDK": {"baseId": "L11", "baseCode": "FDK"},
    "KFLL": {"baseId": "P84", "baseCode": "FLL"},
    "KFOK": {"baseId": "P00", "baseCode": "FOK"},
    "KFSD": {"baseId": "L08", "baseCode": "FSD"},
    "KFSM": {"baseId": "B80", "baseCode": "FSM"},
    "KFTY": {"baseId": "I71", "baseCode": "FTY"},
    "KFXE": {"baseId": "B95", "baseCode": "FXE"},
    "KGEG": {"baseId": "L56", "baseCode": "GEG"},
    "KGRR": {"baseId": "L38", "baseCode": "GRR"},
    "KGSO": {"baseId": "L22", "baseCode": "GSO"},
    "KHOU": {"baseId": "I72", "baseCode": "HOU"},
    "KHPN (P57)": {"baseId": "P57", "baseCode": "HPN"},
    "KHPN (P60)": {"baseId": "P60", "baseCode": "HPN"},
    "KHSV": {"baseId": "P25", "baseCode": "HSV"},
    "KHWD": {"baseId": "I53", "baseCode": "HWD"},
    "KHXD": {"baseId": "P37", "baseCode": "HXD"},
    "KIAD": {"baseId": "P02", "baseCode": "IAD"},
    "KIAH": {"baseId": "L46", "baseCode": "IAH"},
    "KICT": {"baseId": "I75", "baseCode": "ICT"},
    "KIND": {"baseId": "P85", "baseCode": "IND"},
    "KINT": {"baseId": "L40", "baseCode": "INT"},
    "KISM": {"baseId": "I70", "baseCode": "ISM"},
    "KIXD": {"baseId": "G42", "baseCode": "IXD"},
    "KJAX": {"baseId": "P73", "baseCode": "JAX"},
    "KLAS": {"baseId": "H10", "baseCode": "LAS"},
    "KLAX": {"baseId": "L29", "baseCode": "LAX"},
    "KLEX": {"baseId": "B83", "baseCode": "LEX"},
    "KLFT": {"baseId": "L12", "baseCode": "LFT"},
    "KLGB": {"baseId": "P31", "baseCode": "LGB"},
    "KLIT": {"baseId": "B90", "baseCode": "LIT"},
    "KLRD": {"baseId": "L25", "baseCode": "LRD"},
    "KLUK": {"baseId": "L15", "baseCode": "LUK"},
    "KMAF": {"baseId": "L55", "baseCode": "MAF"},
    "KMCI": {"baseId": "G43", "baseCode": "MCI"},
    "KMCO": {"baseId": "P08", "baseCode": "MCO"},
    "KMDW": {"baseId": "B25", "baseCode": "MDW"},
    "KMEM": {"baseId": "P86", "baseCode": "MEM"},
    "KMHT": {"baseId": "P56", "baseCode": "MHT"},
    "KMIA": {"baseId": "L23", "baseCode": "MIA"},
    "KMKC": {"baseId": "G41", "baseCode": "MKC"},
    "KMKE": {"baseId": "V50", "baseCode": "MKE"},
    "KMMU": {"baseId": "P67", "baseCode": "MMU"},
    "KMOB": {"baseId": "P26", "baseCode": "MOB"},
    "KMQS": {"baseId": "L53", "baseCode": "MQS"},
    "KMSP": {"baseId": "V51", "baseCode": "MSP"},
    "KMSY": {"baseId": "P36", "baseCode": "MSY"},
    "KNEW": {"baseId": "L13", "baseCode": "NEW"},
    "KOAK": {"baseId": "L30", "baseCode": "OAK"},
    "KOMA": {"baseId": "P44", "baseCode": "OMA"},
    "KOPF": {"baseId": "L26", "baseCode": "OPF"},
    "KORD": {"baseId": "B21", "baseCode": "ORD"},
    "KORF": {"baseId": "L50", "baseCode": "ORF"},
    "KPDK": {"baseId": "P65", "baseCode": "PDK"},
    "KPHK": {"baseId": "L33", "baseCode": "PHK"},
    "KPIE": {"baseId": "P11", "baseCode": "PIE"},
    "KPSP": {"baseId": "P87", "baseCode": "PSP"},
    "KPVU": {"baseId": "B92", "baseCode": "PVU"},
    "KPWK": {"baseId": "P69", "baseCode": "PWK"},
    "KRDU": {"baseId": "L41", "baseCode": "RDU"},
    "KROA": {"baseId": "L51", "baseCode": "ROA"},
    "KRST": {"baseId": "P39", "baseCode": "RST"},
    "KSAF": {"baseId": "L00", "baseCode": "SAF"},
    "KSAN": {"baseId": "L21", "baseCode": "SAN"},
    "KSAT (I74)": {"baseId": "I74", "baseCode": "SAT"},
    "KSAT (L44)": {"baseId": "L44", "baseCode": "SAT"},
    "KSAV": {"baseId": "B45", "baseCode": "SAV"},
    "KSBA": {"baseId": "P71", "baseCode": "SBA"},
    "KSBN": {"baseId": "P13", "baseCode": "SBN"},
    "KSDL": {"baseId": "P58", "baseCode": "SDL"},
    "KSEA": {"baseId": "B16", "baseCode": "SEA"},
    "KSFO": {"baseId": "P88", "baseCode": "SFO"},
    "KSHV": {"baseId": "B81", "baseCode": "SHV"},
    "KSJC": {"baseId": "P05", "baseCode": "SJC"},
    "KSLC": {"baseId": "B91", "baseCode": "SLC"},
    "KSTL": {"baseId": "P22", "baseCode": "STL"},
    "KSTP": {"baseId": "P38", "baseCode": "STP"},
    "KSUS": {"baseId": "B89", "baseCode": "SUS"},
    "KSWF": {"baseId": "P28", "baseCode": "SWF"},
    "KTEB (I52)": {"baseId": "I52", "baseCode": "TEB"},
    "KTEB (L18)": {"baseId": "L18", "baseCode": "TEB"},
    "KTEB (P62)": {"baseId": "P62", "baseCode": "TEB"},
    "KTMB": {"baseId": "L24", "baseCode": "TMB"},
    "KTPA": {"baseId": "L34", "baseCode": "TPA"},
    "KTTN": {"baseId": "L58", "baseCode": "TTN"},
    "KTXK": {"baseId": "B79", "baseCode": "TXK"},
    "KTYS": {"baseId": "B87", "baseCode": "TYS"},
    "KVNY (B77)": {"baseId": "B77", "baseCode": "VNY"},
    "KVNY (I77)": {"baseId": "I77", "baseCode": "VNY"},
    "KVNY (VNE)": {"baseId": "VNE", "baseCode": "VNY"}
}

DEFAULT_FLEET = ["N730K", "N265K", "N316K", "N681K"]

# Fixed Account Credentials
ACCOUNT_NUMBER = "3951"
ACCOUNT_ID = "1cdf46c1-ee12-df11-b019-005056a16799"
MODEL_NUMBER = "0"

# Sidebar Controls
st.sidebar.header("Parameters & Configuration")

station_mode = st.sidebar.radio("Airport Selection Mode", ["Select from List", "Type ICAO Code", "All Airports"])
if station_mode == "Select from List":
    selected_station = st.sidebar.selectbox("Select Airport ICAO", list(ALL_STATIONS.keys()), index=0)
    stations_to_query = [selected_station]
elif station_mode == "Type ICAO Code":
    custom_icao = st.sidebar.text_input("Enter Airport ICAO Code (e.g., KTEB, KBOS)", value="").strip().upper()
    if custom_icao:
        stations_to_query = [custom_icao]
    else:
        st.sidebar.warning("Please enter an ICAO code.")
        stations_to_query = []
else:
    stations_to_query = list(ALL_STATIONS.keys())

aircraft_mode = st.sidebar.radio("Aircraft Selection Mode", ["Single Aircraft", "All Aircraft (Fleet)"])
if aircraft_mode == "Single Aircraft":
    selected_aircraft = st.sidebar.selectbox("Select Aircraft Registration", DEFAULT_FLEET, index=0)
    aircraft_to_query = [selected_aircraft]
else:
    aircraft_to_query = DEFAULT_FLEET

selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())

# Action Button
fetch_button = st.sidebar.button("🔍 Fetch Live Fees", type="primary", use_container_width=True)

def extract_signature_fees(api_response):
    extracted = {
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

    items_list = []
    if isinstance(api_response, dict):
        raw_data = api_response.get("data", [])
        if isinstance(raw_data, list):
            items_list = raw_data

    for s_item in items_list:
        if not isinstance(s_item, dict):
            continue
        description = str(s_item.get("description", "")).upper()
        src_code = str(s_item.get("srcProductCode", "")).upper()
        price = s_item.get("customerPrice")
        
        val_str = "N/A"
        if price is not None and str(price).strip() != "":
            try:
                val_str = f"{float(price):.2f}"
            except ValueError:
                val_str = str(price)

        if "HANDLING" in description or "HANDLING" in src_code:
            extracted["handling"] = val_str
            details = s_item.get("serviceDetails", "")
            if details:
                match = re.search(r'(\d+)\s*(?:US\s*)?Gallon', details, re.IGNORECASE)
                if match:
                    extracted["waiver_min_gallons"] = match.group(1)
        elif "INFRASTRUCTURE" in description or "INFRA" in src_code:
            extracted["infra"] = val_str
        elif "GROUND POWER UNIT" in description and "START" not in description:
            extracted["gpu"] = val_str
        elif "HANGAR" in description or "HANGER" in src_code:
            extracted["hangar"] = val_str
        elif "LAVATORY" in description or "LAV" in src_code:
            extracted["lav"] = val_str

    return extracted

def fetch_live_signature_fees(stations_list, aircraft_list, date_val):
    formatted_date = date_val.strftime("%m/%d/%Y")
    encoded_date = formatted_date.replace("/", "%2F")
    records = []

    total_requests = len(stations_list) * len(aircraft_list)
    completed = 0

    # UI Feedback Containers
    progress_bar = st.progress(0)
    status_box = st.status("🚀 **Initializing API Data Fetch...**", expanded=True)
    
    with status_box:
        log_placeholder = st.empty()

        for icao in stations_list:
            clean_icao = icao.strip().upper()
            
            if clean_icao in ALL_STATIONS:
                station_info = ALL_STATIONS[clean_icao]
            else:
                base_code = clean_icao[-3:] if len(clean_icao) >= 3 else clean_icao
                station_info = {"baseId": clean_icao, "baseCode": base_code}
            
            for reg in aircraft_list:
                clean_reg = reg.strip().upper()
                if not clean_reg:
                    continue
                
                completed += 1
                progress_pct = completed / total_requests
                progress_bar.progress(progress_pct)
                
                # Update status message with current ICAO & Registration
                log_placeholder.markdown(
                    f"Fetching **{completed}/{total_requests}**: Station **`{clean_icao}`** | Aircraft **`{clean_reg}`**..."
                )
                
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
                    if res.status_code == 200:
                        response_json = res.json()
                except Exception:
                    pass

                parsed = extract_signature_fees(response_json)
                
                # Check if hangar fee is 0.00 or N/A
                hangar_val = parsed["hangar"]
                display_hangar = "Call FBO" if hangar_val in ["0.00", "N/A"] else hangar_val

                records.append({
                    "ICAO": clean_icao,
                    "Aircraft Reg": clean_reg,
                    "Date": formatted_date,
                    "Handling Fee": parsed["handling"],
                    "Waiver Min GLL": parsed["waiver_min_gallons"],
                    "Infrastructure Fee": parsed["infra"],
                    "GPU": parsed["gpu"],
                    "Hangar": display_hangar,
                    "Lav Service": parsed["lav"]
                })

        # Update status box to completed state
        status_box.update(label=f"✅ **Data Fetch Completed! ({total_requests}/{total_requests} requests processed)**", state="complete", expanded=False)

    return records

# Handle data fetching on button click and persist results across rerun
if fetch_button:
    if not stations_to_query:
        st.error("Please enter or select a valid airport ICAO code first.")
    else:
        st.session_state["fbo_records"] = fetch_live_signature_fees(
            stations_to_query, aircraft_to_query, selected_date
        )

# Display Results
if "fbo_records" in st.session_state and st.session_state["fbo_records"]:
    st.subheader("📊 Live FBO Service Fees Table")
    df_results = pd.DataFrame(st.session_state["fbo_records"])

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
else:
    st.info("Configure parameters in the sidebar and click **'🔍 Fetch Live Fees'** to retrieve data.")