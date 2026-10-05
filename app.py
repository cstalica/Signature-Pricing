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
    "KFOK": {"baseId": "P0