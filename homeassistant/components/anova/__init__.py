"""The Anova integration."""

import asyncio
import logging
from typing import TYPE_CHECKING

from anova_wifi import (
    AnovaApi,
    APCWifiDevice,
    InvalidLogin,
    NoDevicesFound,
    WebsocketFailure,
)
from anova_wifi.exceptions import LoginUnreachable

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_call_later

from .coordinator import AnovaConfigEntry, AnovaCoordinator, AnovaData

PLATFORMS = [Platform.SENSOR]
RECONNECT_RETRY_DELAY = 30

_LOGGER = logging.getLogger(__name__)


@callback
def _async_setup_disconnect_listener(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
) -> None:
    """Register a done callback on the websocket listener task to reconnect on drop."""
    ws_handler = entry.runtime_data.api.websocket_handler
    if ws_handler is None or ws_handler._message_listener is None:  # noqa: SLF001
        return

    @callback
    def _async_on_message_listener_done(task: asyncio.Future[None]) -> None:
        if task.cancelled():
            return
        if entry.state is not ConfigEntryState.LOADED:
            return
        entry.async_create_background_task(
            hass,
            _async_reconnect_websocket(hass, entry),
            "anova_websocket_reconnect",
        )

    ws_handler._message_listener.add_done_callback(  # noqa: SLF001
        _async_on_message_listener_done
    )


@callback
def _async_schedule_reconnect_retry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
) -> None:
    """Schedule a reconnect attempt after a delay."""

    @callback
    def _retry(_now: object) -> None:
        if entry.state is not ConfigEntryState.LOADED:
            return
        entry.async_create_background_task(
            hass,
            _async_reconnect_websocket(hass, entry),
            "anova_websocket_reconnect",
        )

    cancel = async_call_later(hass, RECONNECT_RETRY_DELAY, _retry)
    entry.async_on_unload(cancel)


async def _async_reconnect_websocket(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
) -> None:
    """Reconnect the Anova websocket and re-wire device coordinators."""
    _LOGGER.warning("Anova websocket connection lost, attempting to reconnect")
    try:
        await entry.runtime_data.api.create_websocket()
    except WebsocketFailure:
        try:
            await entry.runtime_data.api.authenticate()
        except InvalidLogin as err:
            _LOGGER.error("Anova re-authentication failed: %s", err)
            return
        except LoginUnreachable as err:
            _LOGGER.warning("Failed to re-authenticate with Anova: %s", err)
            _async_schedule_reconnect_retry(hass, entry)
            return
        try:
            await entry.runtime_data.api.create_websocket()
        except (NoDevicesFound, WebsocketFailure) as err:
            _LOGGER.warning("Failed to reconnect to Anova websocket: %s", err)
            _async_schedule_reconnect_retry(hass, entry)
            return
    except NoDevicesFound as err:
        _LOGGER.warning("Failed to reconnect to Anova websocket: %s", err)
        _async_schedule_reconnect_retry(hass, entry)
        return

    ws_handler = entry.runtime_data.api.websocket_handler
    if ws_handler is None:
        return

    for coordinator in entry.runtime_data.coordinators:
        device = ws_handler.devices.get(coordinator.device_unique_id)
        if device is not None:
            coordinator.anova_device = device
            device.set_update_listener(coordinator.async_set_updated_data)

    _async_setup_disconnect_listener(hass, entry)


async def async_setup_entry(hass: HomeAssistant, entry: AnovaConfigEntry) -> bool:
    """Set up Anova from a config entry."""
    api = AnovaApi(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await api.authenticate()
    except InvalidLogin as err:
        _LOGGER.error(
            "Login was incorrect - please log back in through the config flow. %s", err
        )
        return False
    assert api.jwt
    try:
        await api.create_websocket()
    except NoDevicesFound as err:
        # Can later setup successfully and spawn a repair.
        raise ConfigEntryNotReady(
            "No devices were found on the websocket, perhaps you"
            " don't have any devices on this account?"
        ) from err
    except WebsocketFailure as err:
        raise ConfigEntryNotReady("Failed connecting to the websocket.") from err
    # Create a coordinator per device, if the device is offline, no data will be on the
    # websocket, and the coordinator should auto mark as unavailable. But as long as
    # the websocket successfully connected, config entry should setup.
    devices: list[APCWifiDevice] = []
    if TYPE_CHECKING:
        # api.websocket_handler can't be None after successfully creating the
        # websocket client
        assert api.websocket_handler is not None
    devices = list(api.websocket_handler.devices.values())
    coordinators = [AnovaCoordinator(hass, entry, device) for device in devices]
    entry.runtime_data = AnovaData(api_jwt=api.jwt, coordinators=coordinators, api=api)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_setup_disconnect_listener(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AnovaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        ws_handler = entry.runtime_data.api.websocket_handler
        if ws_handler is not None and ws_handler._message_listener is not None:  # noqa: SLF001
            ws_handler._message_listener.cancel()  # noqa: SLF001
        await entry.runtime_data.api.disconnect_websocket()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: AnovaConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version == 1 and entry.minor_version == 1:
        new_data = {**entry.data}
        if CONF_DEVICES in new_data:
            new_data.pop(CONF_DEVICES)

        hass.config_entries.async_update_entry(entry, data=new_data, minor_version=2)

    _LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True
