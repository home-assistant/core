"""The jvc_projector integration."""

from __future__ import annotations

import logging

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_READONLY, DOMAIN
from .coordinator import JvcProjectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    device = JvcProjector(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await device.connect(True)
    except JvcProjectorConnectError as err:
        await device.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_HOST]}"
        ) from err
    except JvcProjectorAuthError as err:
        await device.disconnect()
        raise ConfigEntryAuthFailed("Password authentication failed") from err

    coordinator = JvcProjectorDataUpdateCoordinator(hass, device, entry.data[CONF_NAME])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def disconnect(event: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
    # We remove the remote if is ReadOnly
    if entry.data[CONF_READONLY] is False:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.REMOTE])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_sensor = await hass.config_entries.async_unload_platforms(
        entry, Platform.SENSOR
    )

    unload_binarysensor = await hass.config_entries.async_unload_platforms(
        entry, Platform.BINARY_SENSOR
    )

    if entry.data[CONF_READONLY] is False:
        unload_remote = await hass.config_entries.async_unload_platforms(
            entry, Platform.REMOTE
        )
        unload_ok = unload_sensor and unload_binarysensor and unload_remote
    else:
        unload_ok = unload_sensor and unload_binarysensor

    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id].device.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
