"""The Control4 integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
import json
import logging

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials
from pyControl4.websocket import C4Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_ACCOUNT,
    CONF_CONFIG_LISTENER,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_DIRECTOR_TOKEN_EXPIRATION,
    CONF_WEBSOCKET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Control4 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    config = entry.data

    await refresh_tokens(hass, entry)
    account = entry_data[CONF_ACCOUNT]
    director = entry_data[CONF_DIRECTOR]
    # Copy controller unique id from config to entry_data for use by entities
    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    entry_data[CONF_CONTROLLER_UNIQUE_ID] = controller_unique_id

    websocket_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    websocket = C4Websocket(
        config[CONF_HOST], director.director_bearer_token, websocket_session
    )
    entry_data[CONF_WEBSOCKET] = websocket
    await websocket.sio_connect()

    # Add Control4 controller to device registry
    controller_href = (await account.getAccountControllers())["href"]
    entry_data[CONF_DIRECTOR_SW_VERSION] = await account.getControllerOSVersion(
        controller_href
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

    entry_data[CONF_CONFIG_LISTENER] = entry.add_update_listener(update_listener)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def update_listener(hass, config_entry):
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
    _LOGGER.debug("Getting items of category: %s", category)
    director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
    return_list = await director.getAllItemsByCategory(category)
    return json.loads(return_list)


async def refresh_tokens(hass: HomeAssistant, entry: ConfigEntry):
    """Store updated authentication and director tokens in hass.data."""
    config = entry.data
    account_session = aiohttp_client.async_get_clientsession(hass)

    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD], account_session)
    try:
        await account.getAccountBearerToken()
    except client_exceptions.ClientError as exception:
        _LOGGER.error("Error connecting to Control4 account API: %s", exception)
        raise ConfigEntryNotReady from exception
    except BadCredentials as exception:
        _LOGGER.error(
            "Error authenticating with Control4 account API, incorrect username or password: %s",
            exception,
        )
        return False

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    director_token_dict = await account.getDirectorBearerToken(controller_unique_id)
    director_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)

    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], director_session
    )

    _LOGGER.debug("Saving new tokens in hass data")
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[CONF_ACCOUNT] = account
    entry_data[CONF_DIRECTOR] = director
    entry_data[CONF_DIRECTOR_TOKEN_EXPIRATION] = director_token_dict["validSeconds"]
    callable_partial = partial(refresh_tokens_callable, hass, entry)
    async_call_later(
        hass,
        entry_data[CONF_DIRECTOR_TOKEN_EXPIRATION],
        callable_partial,
    )


def refresh_tokens_callable(hass: HomeAssistant, entry: ConfigEntry) -> Callable:
    """Callable wrapper of refresh_tokens()."""
    return asyncio.run(refresh_tokens(hass, entry))


class Control4Entity(Entity):
    """Base entity for Control4."""

    def __init__(
        self,
        entry_data: dict,
        entry: ConfigEntry,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        device_area: str,
        device_attributes: dict,
    ) -> None:
        """Initialize a Control4 entity."""
        super().__init__()
        self.entry = entry
        self.entry_data = entry_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._controller_unique_id = entry_data[CONF_CONTROLLER_UNIQUE_ID]
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id
        self._device_area = device_area
        self._extra_state_attributes = device_attributes

    async def async_added_to_hass(self):
        """Sync with HASS."""
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(
            self.entry_data[CONF_WEBSOCKET].add_device_callback,
            self._idx,
            self._update_callback,
        )
        _LOGGER.debug("Registering device %s for callback", self._device_id)
        return True

    async def _update_callback(self, device, message):
        _LOGGER.debug(message)

        if message["evtName"] == "OnDataToUI":
            data = message["data"]
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        for k, val in value.items():
                            self._extra_state_attributes[k] = val
                    else:
                        self._extra_state_attributes[key.upper()] = value
        _LOGGER.debug("Message for device %s", device)
        self.schedule_update_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device of entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device=(DOMAIN, self._controller_unique_id),
            suggested_area=self._device_area,
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return Extra state attributes."""
        return self._extra_state_attributes

    @property
    def should_poll(self) -> bool:
        """Disable polling (could have a config for this)."""
        return False
