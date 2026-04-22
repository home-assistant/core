"""The Russound RNET integration."""

from __future__ import annotations

import logging

from aiorussound.connection import (
    RussoundConnectionHandler,
    RussoundSerialConnectionHandler,
    RussoundTcpConnectionHandler,
)
from aiorussound.rnet.client import RussoundRNETClient

from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_CONTROLLERS, DEFAULT_BAUDRATE, DOMAIN, RNET_MODELS, TYPE_TCP
from .coordinator import RussoundRNETConfigEntry, RussoundRNETCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Set up Russound RNET from a config entry."""
    handler: RussoundConnectionHandler
    if entry.data[CONF_TYPE] == TYPE_TCP:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        handler = RussoundTcpConnectionHandler(host, port)
    else:
        device = entry.data[CONF_DEVICE]
        handler = RussoundSerialConnectionHandler(device, DEFAULT_BAUDRATE)

    client = RussoundRNETClient(handler)
    coordinator = RussoundRNETCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Create a parent device for each controller
    model_key = entry.data.get(CONF_MODEL, "")
    model = RNET_MODELS.get(model_key)
    device_registry = dr.async_get(hass)
    for controller_id in range(1, entry.data.get(CONF_CONTROLLERS, 1) + 1):
        via_device = None
        if controller_id != 1:
            via_device = (DOMAIN, f"{entry.unique_id}_1")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.unique_id}_{controller_id}")},
            manufacturer="Russound",
            name=f"{model.name} Controller {controller_id}"
            if model
            else f"Controller {controller_id}",
            model=model.name if model else None,
            via_device=via_device,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
