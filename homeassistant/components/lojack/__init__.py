"""The LoJack integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import LOGGER
from .coordinator import LoJackCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


@dataclass
class LoJackData:
    """Data class for LoJack runtime data."""

    client: LoJackClient
    coordinator: LoJackCoordinator
    devices: dict[str, Any]  # Device ID -> LoJack API device object


type LoJackConfigEntry = ConfigEntry[LoJackData]


async def async_setup_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Set up LoJack from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        client = await LoJackClient.create(username, password)
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ApiError as err:
        raise ConfigEntryNotReady(f"API error during setup: {err}") from err

    devices: dict[str, Any] = {}
    coordinator = LoJackCoordinator(hass, client, entry, devices)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LoJackData(
        client=client, coordinator=coordinator, devices=devices
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        try:
            await entry.runtime_data.client.close()
        except Exception:  # noqa: BLE001 - Cleanup during unload should not fail
            LOGGER.debug("Error closing LoJack client during unload", exc_info=True)

    return unload_ok
