"""Constants for PlayStation 4."""

ATTR_MEDIA_IMAGE_URL = "media_image_url"
CONFIG_ENTRY_VERSION = 3
DEFAULT_NAME = "PlayStation 4"
DEFAULT_REGION = "United States"
DEFAULT_ALIAS = "Home-Assistant"
DOMAIN = "ps4"
GAMES_FILE = ".ps4-games.{}.json"
PS4_DATA = "ps4_data"

COMMANDS = ("up", "down", "right", "left", "enter", "back", "option", "ps", "ps_hold")

# Deprecated used for logger/backwards compatibility from 0.89
REGIONS = ["R1", "R2", "R3", "R4", "R5"]

COUNTRYCODE_NAMES = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CO": "Columbia",
    "CR": "Costa Rica",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "DK": "Denmark",
    "EC": "Ecuador",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "GT": "Guatemala",
    "HK": "Hong Kong",
    "HN": "Honduras",
    "HR": "Croatia",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IS": "Iceland",
    "IT": "Italy",
    "JP": "Japan",
    "KW": "Kuwait",
    "LB": "Lebanon",
    "LU": "Luxembourg",
    "MT": "Malta",
    "MX": "Mexico",
    # spelling error compatibility with pyps4_2ndscreen.media_art.COUNTRIES
    "MY": "Maylasia",
    "NI": "Nicaragua",
    "NL": "Nederland",
    "NO": "Norway",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SV": "El Salvador",
    "TH": "Thailand",
    "TR": "Turkey",
    "TW": "Taiwan",
    "UA": "Ukraine",
    "US": "United States",
    "ZA": "South Africa",
}
