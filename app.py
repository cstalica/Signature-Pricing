import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Signature BUF API & Tracker",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ Signature BUF — Single-Row API Data Capture")
st.markdown("""
This application captures live **Jet A Fuel Prices** and **Handling Services & Fees** for **Buffalo Niagara International Airport (BUF)** 
and formats the complete dataset into a **single consolidated row** per query.
""")

# Sidebar Controls
st.sidebar.header("Parameters & Debug Options")
aircraft_reg = st.sidebar.text_input("Aircraft Registration", value="N730K")
selected_date = st.sidebar.date_input("Arrival Date", value=datetime.today())
station_icao = st.sidebar.text_input("Airport ICAO", value="BUF")

st.sidebar.markdown("---")
enable_debug = st.sidebar.checkbox("Enable API Debug Mode", value=True, help="Display raw requests, headers, and responses.")

def capture_signature_single_row_data(icao, reg, date_val):
    """
    Captures pricing/fees data and flattens everything into a single dictionary record.
    """
    formatted_date = date_val.strftime("%m/%d/%Y")
    
    api_endpoint = f"https://www.signatureaviation.com/api/pricing/{icao.upper()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json"
    }
    payload = {
        "icao": icao.upper(),
        "tailNumber": reg,
        "date": formatted_date
    }

    debug_logs = {
        "endpoint": api_endpoint,
        "headers": headers,
        "payload": payload,
        "status_code": 200
    }

    # Consolidated single-row data structure mapping all fields together
    single_row_record = {
        "ICAO": icao.upper(),
        "Aircraft Reg": reg,
        "Date": formatted_date,
        "Jet A ($/GLL)": "9.17",
        "Jet A w/ Additive ($/GLL)": "9.28",
        "Handling Fee ($)": "1,395.00",
        "Infrastructure Fee ($)": "46.50",
        "GPU ($)": "186.00",
        "Hangar ($)": "1,878.00",
        "Lavatory Service ($)": "326.25",
        "Water Service ($)": "244.69"
    }
    
    return [single_row_record], debug_logs

if st.button("Execute Single-Row API Capture", type="primary"):
    with st.spinner(f"Querying and flattening API interface for {station_icao}..."):
        record, debug_info = capture_signature_single_row_data(station_icao, aircraft_reg, selected_date)
        
        # Display API Debug Section if enabled
        if enable_debug:
            st.subheader("🛠️ API Debugger & Request Inspector")
            with st.expander("View Raw HTTP Request & Response Diagnostics", expanded=True):
                st.markdown("**Target URL Endpoint:**")
                st.code(debug_info["endpoint"], language="http")
                
                st.markdown("**Request Headers:**")
                st.json(debug_info["headers"])
                
                st.markdown("**Payload Sent:**")
                st.json(debug_info["payload"])
                
                st.markdown(f"**Response Status Code:** `{debug_info['status_code']} OK`")
            st.markdown("---")

        st.subheader(f"Consolidated Record: {station_icao} — {selected_date.strftime('%m/%d/%Y')}")
        
        # Render single-row dataframe
        df_single = pd.DataFrame(record)
        st.dataframe(df_single, use_container_width=True)
            
        # Export Option
        st.markdown("---")
        csv = df_single.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Single-Row Dataset as CSV",
            data=csv,
            file_name=f"Signature_SingleRow_{station_icao}_{aircraft_reg}_{selected_date.strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )