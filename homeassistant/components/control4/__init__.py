"""The Control4 integration."""
from __future__ import annotations

import json
import logging

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
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_ACCOUNT,
    CONF_CONFIG_LISTENER,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_DIRECTOR_TOKEN_EXPIRATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light"]


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
            "Error authenticating with Control4 account API, incorrect username or password: %s",
            exception,
        )
        return False

    entry_data[CONF_ACCOUNT] = account

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    entry_data[CONF_CONTROLLER_UNIQUE_ID] = controller_unique_id

    director_token_dict = await account.getDirectorBearerToken(controller_unique_id)
    director_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    _LOGGER.debug(director_token_dict)
    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], director_session
    )

    entry_data[CONF_DIRECTOR] = director
    entry_data[CONF_DIRECTOR_TOKEN_EXPIRATION] = director_token_dict["token_expiration"]
    await director.sio_connect()

    # Add Control4 controller to device registry
    controller_href = (await account.getAccountControllers())["href"]
    entry_data[CONF_DIRECTOR_SW_VERSION] = await account.getControllerOSVersion(
        controller_href
    )

    _, model, mac_address = controller_unique_id.split("_", 3)
    entry_data[CONF_DIRECTOR_MODEL] = model.upper()

    device_registry = await dr.async_get_registry(hass)
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

    # Load options from config entry
    entry_data[CONF_SCAN_INTERVAL] = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    entry_data[CONF_CONFIG_LISTENER] = entry.add_update_listener(update_listener)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    _LOGGER.debug("Config entry was updated, rerunning setup")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][CONF_CONFIG_LISTENER]()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", entry.entry_id)

    return unload_ok


async def get_items_of_category(hass: HomeAssistant, entry: ConfigEntry, category: str):
    """Return a list of all Control4 items with the specified category."""
    _LOGGER.debug(f"Getting items of category: {category}")
    director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
    return_list = await director.getAllItemsByCategory(category)
    return json.loads(return_list)


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
        self._name = name
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
            self.entry_data[CONF_DIRECTOR].add_device_callback,
            self._idx,
            self._update_callback,
        )
        _LOGGER.debug(f"Registering device {self._device_id} for callback")
        return True

    async def _update_callback(self, device, message):
        _LOGGER.debug(message)

        if message["evtName"] == "OnDataToUI":
            data = message["data"]
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        for k, v in value.items():
                            self._extra_state_attributes[k.upper()] = value
                    else:
                        self._extra_state_attributes[key.upper()] = value
        _LOGGER.debug(f"Message for device {device}")
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return name of entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return str(self._idx)

    @property
    def device_info(self):
        """Return info of parent Control4 device of entity."""
        return {
            "config_entry_id": self.entry.entry_id,
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": self._device_manufacturer,
            "model": self._device_model,
            "via_device": (DOMAIN, self._controller_unique_id),
            "suggested_area": self._device_area,
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Return Extra state attributes."""
        return self._extra_state_attributes

    @property
    def should_poll(self) -> bool:
        """Disable polling (could have a config for this)."""
        return False
