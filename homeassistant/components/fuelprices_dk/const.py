"""Constants for the Fuelprices.dk integration."""

from homeassistant.const import __version__

DOMAIN = "fuelprices_dk"

CONF_COMPANY = "company"
CONF_STATION = "station"

SUBENTRY_TYPE_STATION = "station"

WEBSITE_URL = "https://fuelprices.dk"
USER_AGENT = f"Home-Assistant/{__version__}"
