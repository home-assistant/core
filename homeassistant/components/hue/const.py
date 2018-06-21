"""Constants for the Hue component."""
import logging

LOGGER = logging.getLogger('homeassistant.components.hue')
DOMAIN = "hue"
API_NUPNP = 'https://www.meethue.com/api/nupnp'

ATTR_DARK = 'dark'
ATTR_DAYLIGHT = 'daylight'
ATTR_LAST_UPDATED = 'last_updated'

ICON_REMOTE = 'mdi:remote'

UOM_HUMIDITY = '%'
UOM_ILLUMINANCE = 'lx'