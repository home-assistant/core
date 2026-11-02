"""Services for aftership."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ADD_TRACKING_SERVICE_SCHEMA,
    DOMAIN,
    REMOVE_TRACKING_SERVICE_SCHEMA,
    UPDATE_TOPIC,
    AfterShipServiceArgument,
)

if TYPE_CHECKING:
    from . import AfterShipConfigEntry


class AfterShipService(StrEnum):
    """Store keys for AfterShip services."""

    ADD_TRACKING = "add_tracking"
    REMOVE_TRACKING = "remove_tracking"


async def handle_add_tracking(call: ServiceCall) -> None:
    """Call when a user adds a new Aftership tracking from Home Assistant."""
    entry: AfterShipConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.trackings.add(
        tracking_number=call.data[AfterShipServiceArgument.TRACKING_NUMBER],
        title=call.data.get(AfterShipServiceArgument.TITLE),
        slug=call.data.get(AfterShipServiceArgument.SLUG),
    )
    async_dispatcher_send(call.hass, UPDATE_TOPIC)


async def handle_remove_tracking(call: ServiceCall) -> None:
    """Call when a user removes an Aftership tracking from Home Assistant."""
    entry: AfterShipConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.trackings.remove(
        tracking_number=call.data[AfterShipServiceArgument.TRACKING_NUMBER],
        slug=call.data[AfterShipServiceArgument.SLUG],
    )
    async_dispatcher_send(call.hass, UPDATE_TOPIC)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    hass.services.async_register(
        DOMAIN,
        AfterShipService.ADD_TRACKING,
        handle_add_tracking,
        schema=ADD_TRACKING_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        AfterShipService.REMOVE_TRACKING,
        handle_remove_tracking,
        schema=REMOVE_TRACKING_SERVICE_SCHEMA,
    )
