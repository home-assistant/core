"""Services for Streamlabs Water."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import StreamlabsConfigEntry

AWAY_MODE_AWAY = "away"
AWAY_MODE_HOME = "home"


class StreamlabsService(StrEnum):
    """Store keys for Streamlabs Water services."""

    SET_AWAY_MODE = "set_away_mode"


class StreamlabsServiceArgument(StrEnum):
    """Store keys for Streamlabs Water service arguments."""

    AWAY_MODE = "away_mode"
    LOCATION_ID = "location_id"


SET_AWAY_MODE_SCHEMA = probatio.Schema(
    {
        probatio.Required(StreamlabsServiceArgument.AWAY_MODE): probatio.In(
            [AWAY_MODE_AWAY, AWAY_MODE_HOME]
        ),
        probatio.Optional(StreamlabsServiceArgument.LOCATION_ID): cv.string,
    }
)


def set_away_mode(call: ServiceCall) -> None:
    """Set the StreamLabsWater Away Mode."""
    entry: StreamlabsConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    coordinator = entry.runtime_data
    coordinator.client.update_location(
        call.data.get(StreamlabsServiceArgument.LOCATION_ID)
        or list(coordinator.data)[0],
        call.data[StreamlabsServiceArgument.AWAY_MODE],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN,
        StreamlabsService.SET_AWAY_MODE,
        set_away_mode,
        schema=SET_AWAY_MODE_SCHEMA,
    )
