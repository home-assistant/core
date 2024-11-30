"""MeteoAlarm constants."""

import logging

DOMAIN = "meteoalarm"
LOGGER = logging.getLogger(__package__)

ATTRIBUTION = "Information provided by MeteoAlarm"

CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"
CONF_PROVINCE = "province"

DEFAULT_NAME = "meteoalarm"
DEFAULT_COUNTRY = "NL"

SUPPORTED_COUNTRIES = {
    "AT": "austria",
    "BE": "belgium",
    "BA": "bosnia-herzegovina",
    "BG": "bulgaria",
    "HR": "croatia",
    "CY": "cyprus",
    "CZ": "czechia",
    "DK": "denmark",
    "EE": "estonia",
    "FI": "finland",
    "FR": "france",
    "DE": "germany",
    "GR": "greece",
    "HU": "hungary",
    "IS": "iceland",
    "IL": "israel",
    "IT": "italy",
    "LV": "latvia",
    "LI": "lithuania",
    "LU": "luxembourg",
    "MT": "malta",
    "ME": "montenegro",
    "NL": "netherlands",
    "MK": "north-macedonia",
    "NO": "norway",
    "PO": "poland",
    "PT": "portugal",
    "RO": "romania",
    "RS": "serbia",
    "SK": "slovakia",
    "SI": "slovenia",
    "ES": "spain",
    "SE": "sweden",
    "CH": "switzerland",
    "UA": "ukraine",
    "GB": "united-kingdom",
}
