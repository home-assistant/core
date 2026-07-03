"""Services for Streamlabs Water."""

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import StreamlabsConfigEntry

ATTR_AWAY_MODE = "away_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
AWAY_MODE_AWAY = "away"
AWAY_MODE_HOME = "home"

CONF_LOCATION_ID = "location_id"

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_AWAY_MODE): vol.In([AWAY_MODE_AWAY, AWAY_MODE_HOME]),
        vol.Optional(CONF_LOCATION_ID): cv.string,
    }
)


def set_away_mode(call: ServiceCall) -> None:
    """Set the StreamLabsWater Away Mode."""
    entry: StreamlabsConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    coordinator = entry.runtime_data
    coordinator.client.update_location(
        call.data.get(CONF_LOCATION_ID) or list(coordinator.data)[0],
        call.data[ATTR_AWAY_MODE],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN, SERVICE_SET_AWAY_MODE, set_away_mode, schema=SET_AWAY_MODE_SCHEMA
    )
