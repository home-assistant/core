"""The Control4 integration."""

import logging
import random
from typing import Any

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import BadCredentials, C4Exception, InvalidCategory
from pyControl4.websocket import C4Websocket

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
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_ACCOUNT,
    CONF_CANCEL_TOKEN_REFRESH_CALLBACK,
    CONF_CONTROLLER_UNIQUE_ID,
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_DIRECTOR_MODEL,
    CONF_DIRECTOR_SW_VERSION,
    CONF_UI_CONFIGURATION,
    CONF_WEBSOCKET,
    DOMAIN,
    RETRY_BACKOFF_MAX_SEC,
    SCHEDULE_REFRESH_ADVANCE_SEC,
    Control4ConfigEntry,
)
from .director_utils import director_get_entry_variables
from .entity import Control4CoordinatorEntity, Control4Entity

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.COVER, Platform.LIGHT, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: Control4ConfigEntry) -> bool:
    """Set up Control4 from a config entry."""
    entry_data: dict[str, Any] = {}
    entry.runtime_data = entry_data

    await refresh_tokens(hass, entry)

    entry_data[CONF_CONTROLLER_UNIQUE_ID] = entry.data[CONF_CONTROLLER_UNIQUE_ID]

    try:
        controller_href = (await entry_data[CONF_ACCOUNT].get_account_controllers())[
            "href"
        ]
    except (TimeoutError, client_exceptions.ClientError) as err:
        raise ConfigEntryNotReady(err) from err

    try:
        entry_data[CONF_DIRECTOR_SW_VERSION] = await entry_data[
            CONF_ACCOUNT
        ].get_controller_os_version(controller_href)
    except (TimeoutError, client_exceptions.ClientError) as err:
        raise ConfigEntryNotReady(err) from err

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

    try:
        entry_data[CONF_DIRECTOR_ALL_ITEMS] = await entry_data[
            CONF_DIRECTOR
        ].get_all_item_info()
    except (TimeoutError, client_exceptions.ClientError) as err:
        raise ConfigEntryNotReady(err) from err

    # Control4 OS 2 controllers do not support the UI configuration endpoint.
    entry_data[CONF_UI_CONFIGURATION] = None
    if int(entry_data[CONF_DIRECTOR_SW_VERSION].split(".")[0]) >= 3:
        try:
            entry_data[CONF_UI_CONFIGURATION] = await entry_data[
                CONF_DIRECTOR
            ].get_ui_configuration()
        except (TimeoutError, client_exceptions.ClientError) as err:
            raise ConfigEntryNotReady(err) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Control4ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data = entry.runtime_data
    _LOGGER.debug("Disconnecting C4Websocket for config entry unload")
    await entry_data[CONF_WEBSOCKET].sio_disconnect()
    _LOGGER.debug("Cancelling scheduled token refresh for config entry unload")
    entry_data[CONF_CANCEL_TOKEN_REFRESH_CALLBACK]()
    return unload_ok


async def get_items_of_category(
    hass: HomeAssistant, entry: Control4ConfigEntry, category: str
) -> list[dict[str, Any]]:
    """Return a list of all Control4 items with the specified category."""
    director = entry.runtime_data[CONF_DIRECTOR]
    try:
        return await director.get_all_items_by_category(category)
    except InvalidCategory:
        _LOGGER.warning(
            "Category %s does not exist on this Control4 system, "
            "entities from this domain will not be set up",
            category,
        )
        return []


async def refresh_tokens(hass: HomeAssistant, entry: Control4ConfigEntry) -> None:
    """Obtain fresh account + director tokens, start (or reuse) the WebSocket, and schedule the next refresh."""
    config = entry.data
    session = aiohttp_client.async_get_clientsession(hass)

    account = C4Account(config[CONF_USERNAME], config[CONF_PASSWORD], session)
    try:
        await account.get_account_bearer_token()
    except (TimeoutError, client_exceptions.ClientError) as err:
        raise ConfigEntryNotReady(err) from err
    except BadCredentials as err:
        raise ConfigEntryAuthFailed(err) from err

    controller_unique_id = config[CONF_CONTROLLER_UNIQUE_ID]
    try:
        director_token_dict = await account.get_director_bearer_token(
            controller_unique_id
        )
    except (TimeoutError, client_exceptions.ClientError) as err:
        raise ConfigEntryNotReady(err) from err

    no_verify_session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    director = C4Director(
        config[CONF_HOST], director_token_dict[CONF_TOKEN], no_verify_session
    )

    entry_data = entry.runtime_data
    entry_data[CONF_ACCOUNT] = account
    entry_data[CONF_DIRECTOR] = director

    if not (
        CONF_WEBSOCKET in entry_data
        and isinstance(entry_data[CONF_WEBSOCKET], C4Websocket)
    ):
        connection_tracker = C4WebsocketConnectionTracker(hass, entry)
        websocket = C4Websocket(
            config[CONF_HOST],
            no_verify_session,
            connection_tracker.connect_callback,
            connection_tracker.disconnect_callback,
        )
        entry_data[CONF_WEBSOCKET] = websocket
        logging.getLogger("socketio.client").setLevel(logging.WARNING)
        logging.getLogger("engineio.client").setLevel(logging.WARNING)
        logging.getLogger("charset_normalizer").setLevel(logging.ERROR)

    try:
        await entry_data[CONF_WEBSOCKET].sio_connect(director.director_bearer_token)
    except Exception as err:
        raise ConfigEntryNotReady(err) from err

    delay = max(
        director_token_dict["validSeconds"] - SCHEDULE_REFRESH_ADVANCE_SEC,
        SCHEDULE_REFRESH_ADVANCE_SEC,
    )
    obj = RefreshTokensObject(hass, entry)
    entry_data[CONF_CANCEL_TOKEN_REFRESH_CALLBACK] = async_call_later(
        hass=hass, delay=delay, action=obj.refresh_tokens
    )


class C4WebsocketConnectionTracker:
    """Refresh entity states on WebSocket reconnect and mark entities unavailable on disconnect."""

    def __init__(self, hass: HomeAssistant, entry: Control4ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self._was_disconnected = False

    async def connect_callback(self) -> None:
        """Re-fetch entity state from director after a reconnect."""
        if not self._was_disconnected:
            return
        _LOGGER.info("WebSocket connection to Control4 re-established")
        item_callbacks = self.entry.runtime_data[CONF_WEBSOCKET].item_callbacks
        for item_id, callbacks in item_callbacks.items():
            try:
                item_attributes = await director_get_entry_variables(
                    self.hass, self.entry, item_id
                )
            except TimeoutError, client_exceptions.ClientError, C4Exception:
                _LOGGER.warning(
                    "Failed to refresh item %s after WebSocket reconnect", item_id
                )
                continue
            message = {
                "evtName": "OnDataToUI",
                "iddevice": item_id,
                "data": item_attributes,
            }
            for callback in list(callbacks):
                await callback(item_id, message)
        self._was_disconnected = False

    async def disconnect_callback(self) -> None:
        """Mark all entities unavailable on WebSocket disconnect."""
        _LOGGER.warning(
            "WebSocket connection to Control4 lost, attempting reconnection"
        )
        self._was_disconnected = True
        item_callbacks = self.entry.runtime_data[CONF_WEBSOCKET].item_callbacks
        for item_id, callbacks in item_callbacks.items():
            for callback in list(callbacks):
                await callback(item_id, False)


class RefreshTokensObject:
    """Callable target for async_call_later token refresh with exponential backoff."""

    def __init__(self, hass: HomeAssistant, entry: Control4ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.retries = 0

    async def refresh_tokens(self, _datetime: Any) -> None:
        """Refresh tokens; retry with exponential backoff on failure."""
        try:
            await refresh_tokens(self.hass, self.entry)
        except ConfigEntryNotReady:
            self.retries += 1
            delay = random.uniform(0, min(2**self.retries, RETRY_BACKOFF_MAX_SEC))
            _LOGGER.warning("Token refresh failed, retrying in %.0f seconds", delay)
            self.entry.runtime_data[CONF_CANCEL_TOKEN_REFRESH_CALLBACK] = (
                async_call_later(
                    hass=self.hass, delay=delay, action=self.refresh_tokens
                )
            )


__all__ = ["Control4CoordinatorEntity", "Control4Entity"]
