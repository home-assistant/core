"""Services for the Monoprice Blackbird Matrix Switch integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_BLACKBIRD, DOMAIN


class BlackbirdService(StrEnum):
    """Store keys for Blackbird services."""

    SET_ALL_ZONES = "set_all_zones"


class BlackbirdServiceArgument(StrEnum):
    """Store keys for Blackbird service arguments."""

    SOURCE = "source"


MEDIA_PLAYER_SCHEMA = probatio.Schema(
    {CommonServiceArgument.ENTITY_ID: cv.comp_entity_ids}
)

BLACKBIRD_SETALLZONES_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {probatio.Required(BlackbirdServiceArgument.SOURCE): cv.string}
)


def _service_handle(service: ServiceCall) -> None:
    """Handle for services."""
    entity_ids = service.data.get(CommonServiceArgument.ENTITY_ID)
    source = service.data.get(BlackbirdServiceArgument.SOURCE)
    zones = service.hass.data.get(DATA_BLACKBIRD, {})
    if entity_ids:
        devices = [
            device for device in zones.values() if device.entity_id in entity_ids
        ]

    else:
        devices = zones.values()

    for device in devices:
        if service.service == BlackbirdService.SET_ALL_ZONES:
            device.set_all_zones(source)


def setup_services(hass: HomeAssistant) -> None:
    """Register the blackbird services."""
    hass.services.register(
        DOMAIN,
        BlackbirdService.SET_ALL_ZONES,
        _service_handle,
        schema=BLACKBIRD_SETALLZONES_SCHEMA,
    )
