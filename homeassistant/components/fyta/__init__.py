"""Initialization of FYTA integration."""
from __future__ import annotations

from datetime import datetime
import logging

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import FytaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Fyta integration."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    access_token = entry.data.get("access_token", "")
    expiration = (
        entry.data["expiration"] if "expiration" in entry.data else datetime.now()
    )

    fyta = FytaConnector(username, password, access_token, expiration)

    coordinator = FytaCoordinator(hass, fyta, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if access_token == "" or expiration < datetime.now():
        try:
            await fyta.login()
        except FytaConnectionError as ex:
            raise ConfigEntryNotReady from ex
        except FytaAuthentificationError as ex:
            raise ConfigEntryAuthFailed from ex
        except FytaPasswordError as ex:
            raise ConfigEntryAuthFailed from ex

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if no entities."""

    if device_entry.model == "Controller":
        _LOGGER.error(
            "You cannot delete the Fyta Controller device via the device delete method. %s",
            "Please remove the integration instead.",
        )
        return False
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Fyta entity."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
