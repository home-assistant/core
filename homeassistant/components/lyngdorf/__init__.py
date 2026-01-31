"""The Lyngdorf integration."""

from __future__ import annotations

import logging

from lyngdorf.const import LyngdorfModel
from lyngdorf.device import (
    async_create_receiver,
    async_find_receiver_model,
    lookup_receiver_model,
)

from homeassistant.const import CONF_HOST, CONF_MODEL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_MANUFACTURER, CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS
from .models import LyngdorfConfigEntry, LyngdorfRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Set up Lyngdorf from a config entry."""

    _LOGGER.debug(
        "Setting up config entry: %s for host (%s)",
        config_entry.unique_id,
        config_entry.data[CONF_HOST],
    )

    # Connect to receiver
    _LOGGER.debug(
        "Setting up new connection to (%s):(%s) with ip %s",
        config_entry.data[CONF_MANUFACTURER],
        config_entry.data[CONF_MODEL],
        config_entry.data[CONF_HOST],
    )
    lyngdorf_model: LyngdorfModel | None = lookup_receiver_model(
        config_entry.data[CONF_MODEL]
    )
    if not lyngdorf_model:
        lyngdorf_model = await async_find_receiver_model(config_entry.data[CONF_HOST])
    if not lyngdorf_model:
        raise ConfigEntryError(
            f"Unable to connect to unsupported model {config_entry.data[CONF_MODEL]}"
        )
    receiver = await async_create_receiver(config_entry.data[CONF_HOST], lyngdorf_model)
    await receiver.async_connect()

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer=lyngdorf_model.manufacturer,
        name=config_entry.title,
        serial_number=config_entry.data[CONF_SERIAL_NUMBER],
        model=lyngdorf_model.model,
    )

    config_entry.runtime_data = LyngdorfRuntimeData(
        receiver=receiver,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from Telnet."""
        await receiver.async_disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Unload a config entry."""

    await config_entry.runtime_data.receiver.async_disconnect()
    _LOGGER.debug("disconnected %s", config_entry.runtime_data.receiver.name)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
