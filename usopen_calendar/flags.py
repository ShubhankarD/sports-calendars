from typing import Dict, List, Optional

# 3-letter IOC/NOC → ISO-3166 alpha-2 (extend as needed)
IOC_TO_ISO2: Dict[str, str] = {
    # Americas
    "USA": "US", "CAN": "CA", "MEX": "MX",
    "ARG": "AR", "BRA": "BR", "CHI": "CL", "COL": "CO", "PER": "PE",
    "URU": "UY", "PAR": "PY", "BOL": "BO", "ECU": "EC", "VEN": "VE",
    "CRC": "CR", "PAN": "PA", "GUA": "GT", "HON": "HN", "ESA": "SV", "NCA": "NI", "BIZ": "BZ",
    "CUB": "CU", "DOM": "DO", "HAI": "HT", "JAM": "JM", "TTO": "TT",
    "BAH": "BS", "BAR": "BB", "BER": "BM", "GUY": "GY", "SUR": "SR",
    "PUR": "PR", "ANT": "AG", "DMA": "DM", "GRN": "GD", "LCA": "LC", "VIN": "VC", "SKN": "KN",
    "ARU": "AW", "IVB": "VG", "ISV": "VI", "CAY": "KY",

    # Europe
    "ESP": "ES", "FRA": "FR", "GBR": "GB", "GER": "DE", "ITA": "IT", "NED": "NL",
    "SUI": "CH", "SWE": "SE", "NOR": "NO", "DEN": "DK", "BEL": "BE", "AUT": "AT",
    "POR": "PT", "POL": "PL", "CZE": "CZ", "SVK": "SK", "SLO": "SI", "CRO": "HR", "SRB": "RS",
    "UKR": "UA", "ROU": "RO", "GRE": "GR", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ISL": "IS", "FIN": "FI", "LUX": "LU", "MLT": "MT", "CYP": "CY",
    "ALB": "AL", "ARM": "AM", "AZE": "AZ", "BLR": "BY", "BUL": "BG",
    "EST": "EE", "LAT": "LV", "LTU": "LT", "MDA": "MD", "GEO": "GE",
    "MON": "MC", "LIE": "LI", "AND": "AD", "SMR": "SM",
    "MKD": "MK", "MNE": "ME", "BIH": "BA", "KOS": "XK", "RUS": "RU",

    # Asia / Middle East
    "CHN": "CN", "JPN": "JP", "KOR": "KR", "PRK": "KP",
    "IND": "IN", "PAK": "PK", "BAN": "BD", "NEP": "NP", "BHU": "BT", "MDV": "MV", "SRI": "LK",
    "AFG": "AF", "KAZ": "KZ", "KGZ": "KG", "TJK": "TJ", "UZB": "UZ", "TKM": "TM", "MGL": "MN",
    "IRI": "IR", "IRQ": "IQ", "QAT": "QA", "UAE": "AE", "BRN": "BH", "OMA": "OM",
    "KSA": "SA", "YEM": "YE", "JOR": "JO", "LIB": "LB", "ISR": "IL", "PLE": "PS",
    "TUR": "TR", "CYP": "CY", "KUW": "KW", "SYR": "SY",
    "HKG": "HK", "TPE": "TW",

    # Southeast Asia
    "THA": "TH", "VIE": "VN", "PHI": "PH", "MAS": "MY", "INA": "ID", "SGP": "SG",
    "CAM": "KH", "LAO": "LA", "MYA": "MM", "BRU": "BN", "TLS": "TL",

    # Oceania
    "AUS": "AU", "NZL": "NZ",
    "FIJ": "FJ", "PNG": "PG", "SAM": "WS", "ASA": "AS", "TGA": "TO",
    "SOL": "SB", "VAN": "VU", "NRU": "NR", "KIR": "KI", "TUV": "TV",
    "COK": "CK", "PLW": "PW", "FSM": "FM", "MHL": "MH", "GUM": "GU",

    # Africa
    "EGY": "EG", "MAR": "MA", "TUN": "TN", "ALG": "DZ", "RSA": "ZA",
    "NGR": "NG", "NIG": "NE", "GUI": "GN", "GBS": "GW", "CPV": "CV",
    "SEN": "SN", "GAM": "GM", "GHA": "GH", "CIV": "CI", "BUR": "BF", "SLE": "SL", "LBR": "LR",
    "MLI": "ML", "MTN": "MR", "BEN": "BJ", "TOG": "TG",
    "CMR": "CM", "GAB": "GA", "GEQ": "GQ", "CAF": "CF", "CHA": "TD",
    "CGO": "CG", "COD": "CD",
    "UGA": "UG", "KEN": "KE", "TAN": "TZ", "RWA": "RW", "BDI": "BI", "ETH": "ET",
    "DJI": "DJ", "ERI": "ER", "SOM": "SO", "SUD": "SD", "SSD": "SS",
    "BOT": "BW", "NAM": "NA", "ZAM": "ZM", "ZIM": "ZW",
    "LES": "LS", "SWZ": "SZ", "MAD": "MG", "MAW": "MW", "MOZ": "MZ", "ANG": "AO",
    "STP": "ST", "SEY": "SC", "MRI": "MU", "COM": "KM",
}

def _flag_emoji(iso2: Optional[str]) -> str:
    """Convert ISO2 country code to flag emoji; fallback to tennis ball."""
    if not iso2:
        return "🎾"
    code = iso2.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🎾"
    base = 0x1F1E6
    return chr(base + (ord(code[0]) - 65)) + chr(base + (ord(code[1]) - 65))

def _join_names(team: Optional[list]) -> str:
    """Join A/B display names for a team if present."""
    team = team or [{}]
    t = team[0] if team else {}
    names = [t.get("displayNameA"), t.get("displayNameB")]
    joined = " & ".join([n for n in names if n])
    return joined

def team_flags(team: Optional[list]) -> str:
    """Return one or two flags for a team based on IOC codes in the feed."""
    t = (team or [{}])[0]
    iocs: List[Optional[str]] = [t.get("nationA"), t.get("nationB")]
    isos: List[str] = []
    for ioc in iocs:
        if not ioc:
            continue
        iso = IOC_TO_ISO2.get(ioc.strip().upper())
        if iso and iso not in isos:
            isos.append(iso)
    if not isos:
        return "🎾"
    if len(isos) == 1:
        return _flag_emoji(isos[0])
    return "/".join(_flag_emoji(c) for c in isos[:2])

def team_label(team: Optional[list]) -> str:
    """Compose '<flags> NameA & NameB' using the existing _join_names()."""
    names = _join_names(team)
    return f"{team_flags(team)} {names}".strip()
