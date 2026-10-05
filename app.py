if icao == "OPF":
        return {
            "retail_price": "$9.50",
            "jet_a_tier1": "$6.21",
            "jet_a_tier2": "$6.00",
            "jet_a_tier3": "$5.80",
            "handling": "$1,350.00" if is_heavy else "$810.00",  # Updated from $1,450.00
            "waiver_min_gallons": "520 gal" if is_heavy else "310 gal",
            "infra": "$38.00",
            "gpu": "$132.68",
            "hangar": "$1,200.00" if is_heavy else "$800.00",
            "lav": "$212.00" if is_heavy else "$200.00"
        }