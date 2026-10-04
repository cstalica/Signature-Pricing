def extract_signature_pricing(data):
    extracted = {
        "service_code": "JET-A",
        "service_name": "Jet A (with additive)",
        "retail_price": "N/A",
        "unit_of_measure": "GLL",
        "jet_a_tier1": "N/A",          # 0-300 GLL
        "jet_a_tier1_discount": "N/A",
        "jet_a_tier2": "N/A",          # 301-1200 GLL
        "jet_a_tier2_discount": "N/A",
        "jet_a_tier3": "N/A",          # 1201+ GLL
        "jet_a_tier3_discount": "N/A",
        "handling": "N/A",
        "waiver_min_gallons": "N/A",
        "handling_details": "N/A",
        "infra": "N/A",
        "special_event": "N/A", 
        "gpu": "N/A",
        "hangar": "N/A",
        "lav": "N/A",
        "water": "N/A"
    }

    # Helper function to process fuel objects directly
    def process_fuel_item(item):
        if not isinstance(item, dict):
            return
        
        svc_code = str(item.get("serviceCode", "")).upper()
        svc_name = str(item.get("serviceName", "")).lower()
        prod_name = str(item.get("productName", "")).lower()
        full_str = f"{svc_code} {svc_name} {prod_name}"

        # Skip Avgas/100LL
        if "100ll" in full_str or "avgas" in full_str:
            return

        if "JET-A" in svc_code or "jet" in full_str or "additive" in full_str or not svc_code:
            if item.get("serviceCode"):
                extracted["service_code"] = str(item.get("serviceCode"))
            if item.get("serviceName"):
                extracted["service_name"] = str(item.get("serviceName"))
            if item.get("unitOfMeasure"):
                extracted["unit_of_measure"] = str(item.get("unitOfMeasure"))

            # 1. Extract Retail Price directly
            retail_val = item.get("retailPrice") or item.get("retail_price") or item.get("basePrice")
            if retail_val is not None:
                extracted["retail_price"] = f"{float(retail_val):.2f}"

            # 2. Extract priceTiers or fallback customer price
            tiers = item.get("priceTiers") or item.get("tiers") or item.get("volumeTiers")
            if isinstance(tiers, list) and len(tiers) > 0:
                sorted_tiers = sorted(
                    [t for t in tiers if isinstance(t, dict) and ("price" in t or "customerPrice" in t)],
                    key=lambda x: x.get("minQuantity", 0)
                )
                if len(sorted_tiers) >= 1:
                    t1_price = sorted_tiers[0].get("price") or sorted_tiers[0].get("customerPrice")
                    extracted["jet_a_tier1"] = f"{float(t1_price):.2f}"
                    if "discountAmount" in sorted_tiers[0]:
                        extracted["jet_a_tier1_discount"] = f"{float(sorted_tiers[0]['discountAmount']):.2f}"
                if len(sorted_tiers) >= 2:
                    t2_price = sorted_tiers[1].get("price") or sorted_tiers[1].get("customerPrice")
                    extracted["jet_a_tier2"] = f"{float(t2_price):.2f}"
                    if "discountAmount" in sorted_tiers[1]:
                        extracted["jet_a_tier2_discount"] = f"{float(sorted_tiers[1]['discountAmount']):.2f}"
                if len(sorted_tiers) >= 3:
                    t3_price = sorted_tiers[2].get("price") or sorted_tiers[2].get("customerPrice")
                    extracted["jet_a_tier3"] = f"{float(t3_price):.2f}"
                    if "discountAmount" in sorted_tiers[2]:
                        extracted["jet_a_tier3_discount"] = f"{float(sorted_tiers[2]['discountAmount']):.2f}"
            else:
                cust_price = item.get("customerPrice") or item.get("price") or item.get("discountedPrice")
                if cust_price is not None:
                    extracted["jet_a_tier1"] = f"{float(cust_price):.2f}"
                
                # If retail_price wasn't set explicitly, use cust_price as baseline retail
                if extracted["retail_price"] == "N/A" and cust_price is not None:
                    extracted["retail_price"] = f"{float(cust_price):.2f}"

    # Helper function to process service fee objects directly
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
            if item.get("waiverMinGallons") is not None:
                extracted["waiver_min_gallons"] = str(item.get("waiverMinGallons"))
            waiver_text = item.get("waiverText") or item.get("serviceDetails") or item.get("details") or item.get("notes")
            if waiver_text:
                extracted["handling_details"] = str(waiver_text)
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

    # 1. Primary Direct Parse
    if isinstance(data, dict):
        if "fuelPricing" in data and isinstance(data["fuelPricing"], list):
            for f_item in data["fuelPricing"]:
                process_fuel_item(f_item)
        if "serviceFees" in data and isinstance(data["serviceFees"], list):
            for s_item in data["serviceFees"]:
                process_fee_item(s_item)

    # 2. Recursive Search Fallback (if retail_price or tier1 remained N/A)
    def recursive_traverse(node):
        if isinstance(node, dict):
            process_fuel_item(node)
            process_fee_item(node)
            for v in node.values():
                recursive_traverse(v)
        elif isinstance(node, list):
            for sub_item in node:
                recursive_traverse(sub_item)

    if extracted["retail_price"] == "N/A" or extracted["jet_a_tier1"] == "N/A":
        recursive_traverse(data)

    return extracted