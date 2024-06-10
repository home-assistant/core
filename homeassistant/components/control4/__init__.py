"""The Control4 integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    API_RETRY_TIMES,
    CONF_ACCOUNT,
    CONF_CONFIG_LISTENER,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_UI_CONFIGURATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.MEDIA_PLAYER]


async def call_c4_api_retry(func, *func_args):
    """Call C4 API function and retry on failure."""
    for i in range(API_RETRY_TIMES):
        try:
            return await func(*func_args)
        except client_exceptions.ClientError as exception:
            _LOGGER.error("Error connecting to Control4 account API: %s", exception)
            if i == API_RETRY_TIMES - 1:
                raise ConfigEntryNotReady(exception) from exception


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Control4 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    account_session = aiohttp_client.async_get_clientsession(hass)

    config = entry.data
    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD], account_session)
    try:
        await account.getAccountBearerToken()
    except client_exceptions.ClientError as exception:
        _LOGGER.error("Error connecting to Control4 account API: %s", exception)
        raise ConfigEntryNotReady from exception
    except BadCredentials as exception:
        _LOGGER.error(
            (
                "Error authenticating with Control4 account API, incorrect username or"
                " password: %s"
            ),
            exception,
        )
        return False
    entry_data[CONF_ACCOUNT] = account

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    entry_data[CONF_CONTROLLER_UNIQUE_ID] = controller_unique_id

    director_token_dict = await call_c4_api_retry(
        account.getDirectorBearerToken, controller_unique_id
    )

    director_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], director_session
    )
    entry_data[CONF_DIRECTOR] = director

    controller_href = (await call_c4_api_retry(account.getAccountControllers))["href"]
    entry_data[CONF_DIRECTOR_SW_VERSION] = await call_c4_api_retry(
        account.getControllerOSVersion, controller_href
    )

    _, model, mac_address = controller_unique_id.split("_", 3)
    entry_data[CONF_DIRECTOR_MODEL] = model.upper()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller_unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
        manufacturer="Control4",
        name=controller_unique_id,
        model=entry_data[CONF_DIRECTOR_MODEL],
        sw_version=entry_data[CONF_DIRECTOR_SW_VERSION],
    )

    # Store all items found on controller for platforms to use
    director_all_items = await director.getAllItemInfo()
    director_all_items = json.loads(director_all_items)
    entry_data[CONF_DIRECTOR_ALL_ITEMS] = director_all_items

    # Check if OS version is 3 or higher to get UI configuration
    entry_data[CONF_UI_CONFIGURATION] = None
    if int(entry_data[CONF_DIRECTOR_SW_VERSION].split(".")[0]) >= 3:
        entry_data[CONF_UI_CONFIGURATION] = json.loads(
            await director.getUiConfiguration()
        )

    # Load options from config entry
    entry_data[CONF_SCAN_INTERVAL] = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    entry_data[CONF_CONFIG_LISTENER] = entry.add_update_listener(update_listener)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    _LOGGER.debug("Config entry was updated, rerunning setup")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][CONF_CONFIG_LISTENER]()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", entry.entry_id)

    return unload_ok


async def get_items_of_category(hass: HomeAssistant, entry: ConfigEntry, category: str):
    """Return a list of all Control4 items with the specified category."""
    director_all_items = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_ALL_ITEMS]
    return [
        item
        for item in director_all_items
        if "categories" in item and category in item["categories"]
    ]


class Control4Entity(CoordinatorEntity[Any]):
    """Base entity for Control4."""

    def __init__(
        self,
        entry_data: dict,
        coordinator: DataUpdateCoordinator[Any],
        name: str | None,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
    ) -> None:
        """Initialize a Control4 entity."""
        super().__init__(coordinator)
        self.entry_data = entry_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._controller_unique_id = entry_data[CONF_CONTROLLER_UNIQUE_ID]
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device of entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device=(DOMAIN, self._controller_unique_id),
        )
