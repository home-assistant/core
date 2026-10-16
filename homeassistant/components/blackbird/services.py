"""Services for the Monoprice Blackbird Matrix Switch integration."""

import probatio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_BLACKBIRD, DOMAIN, SERVICE_SETALLZONES

MEDIA_PLAYER_SCHEMA = probatio.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

ATTR_SOURCE = "source"

BLACKBIRD_SETALLZONES_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {probatio.Required(ATTR_SOURCE): cv.string}
)


def _service_handle(service: ServiceCall) -> None:
    """Handle for services."""
    entity_ids = service.data.get(ATTR_ENTITY_ID)
    source = service.data.get(ATTR_SOURCE)
    zones = service.hass.data.get(DATA_BLACKBIRD, {})
    if entity_ids:
        devices = [
            device for device in zones.values() if device.entity_id in entity_ids
        ]

    else:
        devices = zones.values()

    for device in devices:
        if service.service == SERVICE_SETALLZONES:
            device.set_all_zones(source)


def setup_services(hass: HomeAssistant) -> None:
    """Register the blackbird services."""
    hass.services.register(
        DOMAIN,
        SERVICE_SETALLZONES,
        _service_handle,
        schema=BLACKBIRD_SETALLZONES_SCHEMA,
    )
