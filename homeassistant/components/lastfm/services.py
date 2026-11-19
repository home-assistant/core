"""Services for the LastFM integration."""

from typing import Any

import probatio

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ALBUM,
    ATTR_ARTIST,
    ATTR_TIMESTAMP,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_SCROBBLE,
)

SCROBBLE_SCHEMA: dict[Any, Any] = {
    probatio.Required(ATTR_ARTIST): cv.string,
    probatio.Required(ATTR_TITLE): cv.string,
    probatio.Optional(ATTR_ALBUM): cv.string,
    probatio.Optional(ATTR_TIMESTAMP): cv.datetime,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the LastFM services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SCROBBLE,
        entity_domain=SENSOR_DOMAIN,
        schema=SCROBBLE_SCHEMA,
        func="async_scrobble",
    )
