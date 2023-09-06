"""The Husqvarna Automower integration."""
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
import contextlib
import logging
from typing import cast

import aioautomower

from homeassistant.components.application_credentials import DATA_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Husqvarna data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        api_key = None
        ap_storage: dict = cast(dict, hass.data.get("application_credentials"))
        ap_storage_data: dict = ap_storage[DATA_STORAGE].__dict__["data"]
        for k in ap_storage_data:
            api_key = ap_storage_data[k]["client_id"]
        entry_dict = entry.as_dict()
        access_token = entry_dict["data"]["token"]
        scope = entry_dict["data"]["token"]["scope"]
        if "amc:api" not in scope:
            async_create_issue(
                hass,
                DOMAIN,
                "wrong_scope",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="wrong_scope",
            )
        low_energy = False
        self.session = aioautomower.AutomowerSession(api_key, access_token, low_energy)
        self.session.register_token_callback(
            lambda token: hass.config_entries.async_update_entry(
                entry,
                data={"auth_implementation": DOMAIN, CONF_TOKEN: token},
            )
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Husqvarna."""
        try:
            await self.session.connect()
        except AsyncioTimeoutError as error:
            _LOGGER.debug("Asyncio timeout: %s", error)
            raise ConfigEntryNotReady from error
        except Exception as error:
            _LOGGER.debug("Exception in async_setup_entry: %s", error)
            raise ConfigEntryAuthFailed from Exception


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
    # implementation = await async_get_config_entry_implementation(hass, entry)
    coordinator = AutomowerDataUpdateCoordinator(
        hass,
        # implementation,
        entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unload of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    with contextlib.suppress(Exception):
        await coordinator.session.close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
