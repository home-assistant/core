"""The LoJack integration for Home Assistant."""

from __future__ import annotations

import logging

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import LoJackCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type LoJackConfigEntry = ConfigEntry[LoJackCoordinator]


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

    coordinator = LoJackCoordinator(hass, client, entry)
    success = False
    try:
        await coordinator.async_config_entry_first_refresh()
        success = True
    finally:
        if not success:
            try:
                await client.close()
            except Exception:  # noqa: BLE001 - Best-effort cleanup; preserve original exception
                _LOGGER.debug("Error closing LoJack client during setup failure", exc_info=True)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        try:
            await entry.runtime_data.client.close()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error closing LoJack client: %s", err)

    return unload_ok
