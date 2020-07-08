"""The Control4 integration."""
import asyncio
import datetime
import json
import logging
import re

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import Unauthorized
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr, entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ACCOUNT,
    CONF_CONFIG_LISTENER,
    CONF_CONTROLLER_NAME,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_DIRECTOR_TOKEN_EXPIRATION,
    CONF_LIGHT_COLD_START_TRANSITION_TIME,
    CONF_LIGHT_TRANSITION_TIME,
    DEFAULT_LIGHT_COLD_START_TRANSITION_TIME,
    DEFAULT_LIGHT_TRANSITION_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stub to allow setting up this component.

    Configuration through YAML is not supported at this time.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Control4 from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    config = entry.data
    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD])
    try:
        await account.getAccountBearerToken()
    except client_exceptions.ClientError as exception:
        _LOGGER.error("Error connecting to Control4 account API: %s", exception)
        raise PlatformNotReady()
    hass.data[DOMAIN][entry.entry_id][CONF_ACCOUNT] = account

    controller_name = config[CONF_CONTROLLER_NAME]
    hass.data[DOMAIN][entry.entry_id][CONF_CONTROLLER_NAME] = controller_name

    director_token_dict = await account.getDirectorBearerToken(controller_name)
    director = C4Director(config[CONF_HOST], director_token_dict[CONF_TOKEN])
    hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR] = director
    hass.data[DOMAIN][entry.entry_id][
        CONF_DIRECTOR_TOKEN_EXPIRATION
    ] = director_token_dict["token_expiration"]

    # Add Control4 controller to device registry
    controller_href = (await account.getAccountControllers())["href"]
    hass.data[DOMAIN][entry.entry_id][
        CONF_DIRECTOR_SW_VERSION
    ] = await account.getControllerOSVersion(controller_href)

    result = re.search("_(.*)_", controller_name)
    hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_MODEL] = result.group(1).upper()

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller_name)},
        manufacturer="Control4",
        name=controller_name,
        model=hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_MODEL],
        sw_version=hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_SW_VERSION],
    )

    # Store all items found on controller for platforms to use
    director_all_items = await director.getAllItemInfo()
    director_all_items = json.loads(director_all_items)
    hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_ALL_ITEMS] = director_all_items

    # Load options from config entry
    hass.data[DOMAIN][entry.entry_id][CONF_SCAN_INTERVAL] = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )
    hass.data[DOMAIN][entry.entry_id][CONF_LIGHT_TRANSITION_TIME] = entry.options.get(
        CONF_LIGHT_TRANSITION_TIME, DEFAULT_LIGHT_TRANSITION_TIME
    )
    hass.data[DOMAIN][entry.entry_id][
        CONF_LIGHT_COLD_START_TRANSITION_TIME
    ] = entry.options.get(
        CONF_LIGHT_COLD_START_TRANSITION_TIME, DEFAULT_LIGHT_COLD_START_TRANSITION_TIME
    )

    hass.data[DOMAIN][entry.entry_id][CONF_CONFIG_LISTENER] = entry.add_update_listener(
        update_listener
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    _LOGGER.debug("Config entry was updated, rerunning setup")
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    hass.data[DOMAIN][entry.entry_id][CONF_CONFIG_LISTENER]()
    if unload_ok:
        controller_name = entry.entry_id
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", controller_name)

    return unload_ok


async def get_items_of_category(hass: HomeAssistant, entry: ConfigEntry, category: str):
    """Return a list of all Control4 items with the specified category."""
    director_all_items = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR_ALL_ITEMS]
    return_list = []
    for item in director_all_items:
        if "categories" in item.keys() and category in item["categories"]:
            return_list.append(item)
    return return_list


class Control4Entity(entity.Entity):
    """Base entity for Control4."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        idx: int,
        device_name: str,
        device_manufacturer: str,
        device_model: str,
        device_id: int,
    ):
        """Initialize a Control4 entity."""
        self.entry = entry
        self.account = hass.data[DOMAIN][self.entry.entry_id][CONF_ACCOUNT]
        self.director = hass.data[DOMAIN][self.entry.entry_id][CONF_DIRECTOR]
        self.director_token_expiry = hass.data[DOMAIN][self.entry.entry_id][
            CONF_DIRECTOR_TOKEN_EXPIRATION
        ]
        self._name = name
        self._idx = idx
        self._coordinator = coordinator
        self._controller_name = hass.data[DOMAIN][self.entry.entry_id][
            CONF_CONTROLLER_NAME
        ]
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id

    @property
    def name(self):
        """Return name of entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._idx

    @property
    def device_info(self):
        """Return info of parent Control4 device of entity."""
        return {
            "config_entry_id": self.entry.entry_id,
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": self._device_manufacturer,
            "model": self._device_model,
            "via_device": (DOMAIN, self._controller_name),
        }

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the state of the device."""

        async def _refresh_tokens(self):
            config = self.entry.data
            self.account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD])
            director_token_dict = await self.account.getDirectorBearerToken(
                self._controller_name
            )
            self.director = C4Director(
                config[CONF_HOST], director_token_dict[CONF_TOKEN]
            )
            self.director_token_expiry = director_token_dict["token_expiration"]

            _LOGGER.debug("Saving new tokens in config_entry")
            self.hass.data[DOMAIN][self.entry.entry_id][CONF_ACCOUNT] = self.account
            self.hass.data[DOMAIN][self.entry.entry_id][CONF_DIRECTOR] = self.director
            self.hass.data[DOMAIN][self.entry.entry_id][
                CONF_DIRECTOR_TOKEN_EXPIRATION
            ] = self.director_token_expiry

        if (
            self.director_token_expiry is not None
            and datetime.datetime.now() < self.director_token_expiry
        ):
            _LOGGER.debug("Old director token is still valid. Not getting a new one.")
        else:
            await _refresh_tokens(self)
        try:
            await self._coordinator.async_request_refresh()
        except Unauthorized:
            _LOGGER.warning(
                "Got Unauthorized response from Control4 controller, attempting to refresh tokens."
            )
            await _refresh_tokens(self)
            await self._coordinator.async_request_refresh()
