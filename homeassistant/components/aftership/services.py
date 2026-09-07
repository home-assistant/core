"""Services for aftership."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ADD_TRACKING_SERVICE_SCHEMA,
    CONF_SLUG,
    CONF_TITLE,
    CONF_TRACKING_NUMBER,
    DOMAIN,
    REMOVE_TRACKING_SERVICE_SCHEMA,
    SERVICE_ADD_TRACKING,
    SERVICE_REMOVE_TRACKING,
    UPDATE_TOPIC,
)

if TYPE_CHECKING:
    from . import AfterShipConfigEntry


async def handle_add_tracking(call: ServiceCall) -> None:
    """Call when a user adds a new Aftership tracking from Home Assistant."""
    entry: AfterShipConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.trackings.add(
        tracking_number=call.data[CONF_TRACKING_NUMBER],
        title=call.data.get(CONF_TITLE),
        slug=call.data.get(CONF_SLUG),
    )
    async_dispatcher_send(call.hass, UPDATE_TOPIC)


async def handle_remove_tracking(call: ServiceCall) -> None:
    """Call when a user removes an Aftership tracking from Home Assistant."""
    entry: AfterShipConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.trackings.remove(
        tracking_number=call.data[CONF_TRACKING_NUMBER],
        slug=call.data[CONF_SLUG],
    )
    async_dispatcher_send(call.hass, UPDATE_TOPIC)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TRACKING,
        handle_add_tracking,
        schema=ADD_TRACKING_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TRACKING,
        handle_remove_tracking,
        schema=REMOVE_TRACKING_SERVICE_SCHEMA,
    )
