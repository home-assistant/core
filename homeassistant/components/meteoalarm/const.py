"""Constants for the MeteoAlarm integration."""

from homeassistant.const import Platform

DOMAIN = "meteoalarm"

PLATFORMS = [Platform.BINARY_SENSOR]

CONF_PROVINCE = "province"

DEFAULT_LANGUAGE = "en"
DEFAULT_NAME = "meteoalarm"

ATTRIBUTION = "Information provided by MeteoAlarm"

# MeteoAlarm's countries, from their ISO 3166 code to the name in the feed URL
# (https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-<country>)
COUNTRIES = {
    "AD": "andorra",
    "AT": "austria",
    "BA": "bosnia-herzegovina",
    "BE": "belgium",
    "BG": "bulgaria",
    "CH": "switzerland",
    "CY": "cyprus",
    "CZ": "czechia",
    "DE": "germany",
    "DK": "denmark",
    "EE": "estonia",
    "ES": "spain",
    "FI": "finland",
    "FR": "france",
    "GB": "united-kingdom",
    "GR": "greece",
    "HR": "croatia",
    "HU": "hungary",
    "IE": "ireland",
    "IL": "israel",
    "IS": "iceland",
    "IT": "italy",
    "LT": "lithuania",
    "LU": "luxembourg",
    "LV": "latvia",
    "MD": "moldova",
    "ME": "montenegro",
    "MK": "republic-of-north-macedonia",
    "MT": "malta",
    "NL": "netherlands",
    "NO": "norway",
    "PL": "poland",
    "PT": "portugal",
    "RO": "romania",
    "RS": "serbia",
    "SE": "sweden",
    "SI": "slovenia",
    "SK": "slovakia",
    "UA": "ukraine",
}
