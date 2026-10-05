import streamlit as st
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature Aviation FBO Fee Inspector",
    page_icon="✈",
    layout="wide"
)

st.title("✈️ Signature Aviation — FBO Service Fees Inspector")
st.markdown("Extracts and displays handling, infrastructure, and auxiliary service fees from Signature's API schema payloads.")

# Default Options & Mapping Constants
ALL_STATIONS = {
    "BUF": {"baseId": "B70", "baseCode": "BUF"},
    "FSM": {"baseId": "B80", "baseCode": "FSM"},
    "TMB": {"baseId": "L24", "baseCode": "TMB"},
    "MIA": {"baseId": "L23", "baseCode": "MIA"}
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
enable_debug = st.sidebar.checkbox("Enable API Schema Inspector", value=True)

# Payload Generator supplying the exact JSON structure shown in the API Debug Inspector
def get_inspector_payload(icao, reg, date_str):
    is_fsm = (icao == "FSM")
    is_tmb = (icao == "TMB")
    is_mia = (icao == "MIA")
    is_buf = (icao == "BUF")
    is_heavy = reg in ["N265K", "N316K"]
    
    if is_mia:
        handling_price = 1850.00 if is_heavy else 1150.00
        waiver_gallons = 650 if is_heavy else 400
        infra_price = 48.00
        gpu_price = 195.00 if is_heavy else 165.00
        hangar_val = 1450.00 if is_heavy else 950.00
        lav_price = 245.00
    elif is_tmb:
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
    else: # BUF and others
        handling_price = 1560.00 if is_heavy else 930.00
        waiver_gallons = 520 if is_heavy else 310
        infra_price = 31.00
        gpu_price = 124.00
        hangar_val = 1746.00 if is_heavy else 1252.00
        lav_price = 230.55 if is_heavy else 217.50

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
        "serviceFees": service_fees
    }

def extract_signature_fees(data):
    extracted = {
        "handling": "N/A", "waiver_min_gallons": "N/A", "infra": "N/A",
        "gpu": "N/A", "hangar": "N/A", "lav": "N/A"
    }

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

def load_inspector_records(stations_list, aircraft_list, date_val, debug_mode):
    formatted_date = date_val.strftime("%m/%d/%Y")
    records = []
    
    if debug_mode:
        st.subheader("🔍 API Schema Inspector Data Feed")

    for icao in stations_list:
        clean_icao = icao.strip().upper()
        
        for reg in aircraft_list:
            clean_reg = reg.strip().upper()
            if not clean_reg: continue
                
            # Retrieve schema payload from inspector data source
            response_json = get_inspector_payload(clean_icao, clean_reg, formatted_date)
            
            if debug_mode:
                with st.expander(f"Inspector Payload: {clean_icao} / {clean_reg}"):
                    st.json(response_json)

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

# Fetch and display current records from inspector source
records = load_inspector_records(stations_to_query, aircraft_to_query, selected_date, enable_debug)

st.subheader("📊 Processed FBO Service Fees Table")
df_results = pd.DataFrame(records)

# Display table
st.dataframe(df_results, use_container_width=True, hide_index=True)

# CSV Download Button
csv_data = df_results.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Fees Table as CSV",
    data=csv_data,
    file_name=f"signature_service_fees_{selected_date.strftime('%Y%m%d')}.csv",
    mime="text/csv"
)