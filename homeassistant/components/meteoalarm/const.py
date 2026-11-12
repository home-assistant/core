"""Constants for the MeteoAlarm integration."""

from homeassistant.const import Platform

DOMAIN = "meteoalarm"

PLATFORMS = [Platform.BINARY_SENSOR]

CONF_PROVINCE = "province"

DEFAULT_LANGUAGE = "en"
DEFAULT_NAME = "meteoalarm"

ATTRIBUTION = "Information provided by MeteoAlarm"

# Country names as used in MeteoAlarm's feed URLs
# (https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-<country>)
COUNTRIES = [
    "andorra",
    "austria",
    "belgium",
    "bosnia-herzegovina",
    "bulgaria",
    "croatia",
    "cyprus",
    "czechia",
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "iceland",
    "ireland",
    "israel",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "malta",
    "moldova",
    "montenegro",
    "netherlands",
    "norway",
    "poland",
    "portugal",
    "republic-of-north-macedonia",
    "romania",
    "serbia",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    "switzerland",
    "ukraine",
    "united-kingdom",
]
