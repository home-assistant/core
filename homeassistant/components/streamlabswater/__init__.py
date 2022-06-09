"""Support for Streamlabs Water Monitor devices."""
import logging

from streamlabswater import streamlabswater
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "streamlabswater"

_LOGGER = logging.getLogger(__name__)

ATTR_AWAY_MODE = "away_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
AWAY_MODE_AWAY = "away"
AWAY_MODE_HOME = "home"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_LOCATION_ID = "location_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_LOCATION_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_AWAY_MODE): vol.In([AWAY_MODE_AWAY, AWAY_MODE_HOME])}
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the streamlabs water integration."""

    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    location_id = conf.get(CONF_LOCATION_ID)

    client = streamlabswater.StreamlabsClient(api_key)
    locations = client.get_locations().get("locations")

    if locations is None:
        _LOGGER.error("Unable to retrieve locations. Verify API key")
        return False

    if location_id is None:
        location = locations[0]
        location_id = location["locationId"]
        _LOGGER.info(
            "Streamlabs Water Monitor auto-detected location_id=%s", location_id
        )
    else:
        location = next(
            (loc for loc in locations if location_id == loc["locationId"]), None
        )
        if location is None:
            _LOGGER.error("Supplied location_id is invalid")
            return False

    location_name = location["name"]

    hass.data[DOMAIN] = {
        "client": client,
        "location_id": location_id,
        "location_name": location_name,
    }

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    def set_away_mode(service: ServiceCall) -> None:
        """Set the StreamLabsWater Away Mode."""
        away_mode = service.data.get(ATTR_AWAY_MODE)
        client.update_location(location_id, away_mode)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, set_away_mode, schema=SET_AWAY_MODE_SCHEMA
    )

    return True
