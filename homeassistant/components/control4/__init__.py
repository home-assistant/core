"""The Control4 integration."""
from __future__ import annotations

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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_ACCOUNT,
    CONF_CANCEL_TOKEN_REFRESH_CALLBACK,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_WEBSOCKET,
    DOMAIN,
)
from .director_utils import director_get_entry_variables

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Control4 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    config = entry.data

    await refresh_tokens(hass, entry)
    # Copy controller unique id from config to entry_data for use by entities
    entry_data[CONF_CONTROLLER_UNIQUE_ID] = config[CONF_CONTROLLER_UNIQUE_ID]

    # Add Control4 controller to device registry
    controller_href = (await entry_data[CONF_ACCOUNT].getAccountControllers())["href"]
    entry_data[CONF_DIRECTOR_SW_VERSION] = await entry_data[
        CONF_ACCOUNT
    ].getControllerOSVersion(controller_href)

    _, model, mac_address = entry_data[CONF_CONTROLLER_UNIQUE_ID].split("_", 3)
    entry_data[CONF_DIRECTOR_MODEL] = model.upper()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry_data[CONF_CONTROLLER_UNIQUE_ID])},
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
        manufacturer="Control4",
        name=entry_data[CONF_CONTROLLER_UNIQUE_ID],
        model=entry_data[CONF_DIRECTOR_MODEL],
        sw_version=entry_data[CONF_DIRECTOR_SW_VERSION],
    )

    # Store all items found on controller for platforms to use
    director_all_items = await entry_data[CONF_DIRECTOR].getAllItemInfo()
    director_all_items = json.loads(director_all_items)
    entry_data[CONF_DIRECTOR_ALL_ITEMS] = director_all_items

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    entry_data = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Disconnecting C4Websocket for config entry unload")
    await entry_data[CONF_WEBSOCKET].sio_disconnect()
    _LOGGER.debug("Cancelling scheduled token refresh for config entry unload")
    entry_data[CONF_CANCEL_TOKEN_REFRESH_CALLBACK]()

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
    """Store updated authentication and director tokens in hass.data, and schedule next token refresh."""
    config = entry.data
    verify_ssl_session = aiohttp_client.async_get_clientsession(hass)

    account = C4Account(
        config[CONF_USERNAME], config[CONF_PASSWORD], verify_ssl_session
    )
    try:
        await account.getAccountBearerToken()
    except client_exceptions.ClientError as exception:
        raise ConfigEntryNotReady(exception) from exception
    except BadCredentials as exception:
        raise ConfigEntryAuthFailed(exception) from exception

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    director_token_dict = await account.getDirectorBearerToken(controller_unique_id)
    no_verify_ssl_session = aiohttp_client.async_get_clientsession(
        hass, verify_ssl=False
    )

    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], no_verify_ssl_session
    )

    _LOGGER.debug("Saving new account and director tokens in hass data")
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[CONF_ACCOUNT] = account
    entry_data[CONF_DIRECTOR] = director

    if not (
        CONF_WEBSOCKET in entry_data
        and isinstance(entry_data[CONF_WEBSOCKET], C4Websocket)
    ):
        _LOGGER.debug("First time setup, creating new C4Websocket object")
        connection_tracker = C4WebsocketConnectionTracker(hass, entry)
        websocket = C4Websocket(
            config[CONF_HOST],
            no_verify_ssl_session,
            connection_tracker.connect_callback,
            connection_tracker.disconnect_callback,
        )
        entry_data[CONF_WEBSOCKET] = websocket

        # Silence C4Websocket related loggers, that would otherwise spam INFO logs with debugging messages
        logging.getLogger("socketio.client").setLevel(logging.WARNING)
        logging.getLogger("engineio.client").setLevel(logging.WARNING)
        logging.getLogger("charset_normalizer").setLevel(logging.ERROR)

    _LOGGER.debug("Starting new WebSocket connection")
    await entry_data[CONF_WEBSOCKET].sio_connect(director.director_bearer_token)

    _LOGGER.debug(
        "Registering next token refresh in %s seconds",
        director_token_dict["validSeconds"],
    )
    obj = RefreshTokensObject(hass, entry)
    entry_data[CONF_CANCEL_TOKEN_REFRESH_CALLBACK] = async_call_later(
        hass=hass,
        delay=director_token_dict["validSeconds"],
        action=obj.refresh_tokens,
    )


class C4WebsocketConnectionTracker:
    """Object that provides callables to manually refresh entity states if the Control4 Websocket is disconnected/reconnected."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the state of the connection tracker object."""
        self.hass = hass
        self.entry = entry

        self._was_disconnected = False

    async def connect_callback(self) -> None:
        """Manually refresh entity states when the Websocket is reconnected after a connection drop."""
        if not self._was_disconnected:
            return

        _LOGGER.info("Websocket connection to Control4 reestablished")

        # Refresh state of entities so they are not unavailable anymore
        item_callbacks = self.hass.data[DOMAIN][self.entry.entry_id][
            CONF_WEBSOCKET
        ].item_callbacks
        for item_id, callback in item_callbacks.items():
            item_attributes = await director_get_entry_variables(
                self.hass, self.entry, item_id
            )
            message = {
                "evtName": "OnDataToUI",
                "iddevice": item_id,
                "data": item_attributes,
            }
            await callback(item_id, message)

        self._was_disconnected = False

    async def disconnect_callback(self) -> None:
        """Detect a Websocket connection loss."""
        _LOGGER.warning(
            "Websocket connection to Control4 lost, attempting reconnection"
        )
        self._was_disconnected = True

        # Set all entities to unavailable
        item_callbacks = self.hass.data[DOMAIN][self.entry.entry_id][
            CONF_WEBSOCKET
        ].item_callbacks
        for item_id, callback in item_callbacks.items():
            await callback(item_id, False)


class RefreshTokensObject:
    """Object that provides a callable to refresh tokens."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a RefreshTokensObject by storing the HomeAssistant and ConfigEntry objects required to run refresh_tokens()."""
        self.hass = hass
        self.entry = entry

    async def refresh_tokens(self, datetime):
        """Call the refresh_tokens function to store updated authentication and director tokens in hass.data."""
        # unused datetime parameter is required, since Home Assistant will pass a datetime.datetime object as parameter when calling this function via async_call_later()
        return await refresh_tokens(self.hass, self.entry)


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
        # Disable polling
        self._attr_should_poll = False

    async def async_added_to_hass(self):
        """Add entity to hass. Register Websockets callbacks to receive entity state updates from Control4."""
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(
            self.entry_data[CONF_WEBSOCKET].add_item_callback,
            self._idx,
            self._update_callback,
        )
        _LOGGER.debug("Registering item id %s for callback", self._idx)
        await self.hass.async_add_executor_job(
            self.entry_data[CONF_WEBSOCKET].add_item_callback,
            self._device_id,
            self._update_callback,
        )
        _LOGGER.debug(
            "Registering parent device %s of item id %s for callback",
            self._device_id,
            self._idx,
        )
        return True

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass. Unregister Control4 Websockets callbacks for this entity."""
        _LOGGER.debug("Deregistering callback for item id %s", self._idx)
        self.entry_data[CONF_WEBSOCKET].remove_item_callback(self._idx)
        _LOGGER.debug(
            "Deregistering callback for parent device %s of item id %s",
            self._device_id,
            self._idx,
        )
        self.entry_data[CONF_WEBSOCKET].remove_item_callback(self._device_id)

    async def _update_callback(self, device, message):
        """Update state attributes in hass after receiving a Websocket update for our item id/parent device id."""
        _LOGGER.debug(message)

        # Message will be False when a Websocket disconnect is detected
        if message is False:
            self._attr_available = False
        elif message["evtName"] == "OnDataToUI":
            self._attr_available = True
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
