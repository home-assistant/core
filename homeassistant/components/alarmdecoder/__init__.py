"""Support for AlarmDecoder devices."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from adext import AdExt
from alarmdecoder.devices import SerialDevice, SocketDevice
from alarmdecoder.util import NoDeviceError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_BAUD,
    CONF_DEVICE_PATH,
    DOMAIN,
    PROTOCOL_SERIAL,
    PROTOCOL_SOCKET,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_REL_MESSAGE,
    SIGNAL_RFX_MESSAGE,
    SIGNAL_ZONE_FAULT,
    SIGNAL_ZONE_RESTORE,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
INIT_TIMEOUT = 30
PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

type AlarmDecoderConfigEntry = ConfigEntry[AlarmDecoderData]


@dataclass
class AlarmDecoderData:
    """Runtime data for the AlarmDecoder class."""

    client: AdExt
    remove_update_listener: Callable[[], None]
    remove_stop_listener: Callable[[], None]
    restart: bool
    cancel_retry: CALLBACK_TYPE | None = None
    shutdown: bool = False
    opening: asyncio.Future[Any] | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AlarmDecoderConfigEntry
) -> None:
    """Set up AlarmDecoder config flow."""
    undo_listener = entry.add_update_listener(_update_listener)

    ad_connection = entry.data
    protocol = ad_connection[CONF_PROTOCOL]

    def stop_alarmdecoder(event):
        """Handle the shutdown of AlarmDecoder."""
        _LOGGER.debug("Shutting down alarmdecoder")
        data.restart = False
        controller.close()

    async def open_connection(now=None):
        """Open a connection to AlarmDecoder."""
        data.cancel_retry = None
        # An attempt still connecting when the entry shut down must not revive
        # the controller or schedule another one.
        if data.shutdown:
            return
        try:
            # Shielded so a setup timeout leaves it for shutdown to clean up.
            data.opening = hass.async_add_executor_job(controller.open, baud)
            await asyncio.shield(data.opening)
        except NoDeviceError:
            if data.shutdown:
                return
            _LOGGER.debug("Failed to connect. Retrying in 5 seconds")
            data.cancel_retry = async_call_later(
                hass, timedelta(seconds=5), open_connection
            )
            return
        if data.shutdown:
            return
        _LOGGER.debug("Established a connection with the alarmdecoder")
        data.restart = True

    def handle_closed_connection(event):
        """Restart after unexpected loss of connection."""
        if not data.restart:
            return
        data.restart = False
        _LOGGER.warning("AlarmDecoder unexpectedly lost connection")
        hass.add_job(open_connection)

    def handle_message(sender, message):
        """Handle message from AlarmDecoder."""
        dispatcher_send(hass, SIGNAL_PANEL_MESSAGE, message)

    def handle_rfx_message(sender, message):
        """Handle RFX message from AlarmDecoder."""
        dispatcher_send(hass, SIGNAL_RFX_MESSAGE, message)

    def zone_fault_callback(sender, zone):
        """Handle zone fault from AlarmDecoder."""
        dispatcher_send(hass, SIGNAL_ZONE_FAULT, zone)

    def zone_restore_callback(sender, zone):
        """Handle zone restore from AlarmDecoder."""
        dispatcher_send(hass, SIGNAL_ZONE_RESTORE, zone)

    def handle_rel_message(sender, message):
        """Handle relay or zone expander message from AlarmDecoder."""
        dispatcher_send(hass, SIGNAL_REL_MESSAGE, message)

    baud = ad_connection.get(CONF_DEVICE_BAUD)
    if protocol == PROTOCOL_SOCKET:
        host = ad_connection[CONF_HOST]
        port = ad_connection[CONF_PORT]
        controller = AdExt(SocketDevice(interface=(host, port)))
    if protocol == PROTOCOL_SERIAL:
        path = ad_connection[CONF_DEVICE_PATH]
        controller = AdExt(SerialDevice(interface=path))

    controller.on_message += handle_message
    controller.on_rfx_message += handle_rfx_message
    controller.on_zone_fault += zone_fault_callback
    controller.on_zone_restore += zone_restore_callback
    controller.on_close += handle_closed_connection
    controller.on_expander_message += handle_rel_message

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, stop_alarmdecoder
    )

    data = entry.runtime_data = AlarmDecoderData(
        controller, undo_listener, remove_stop_listener, False
    )

    try:
        async with asyncio.timeout(INIT_TIMEOUT):
            await open_connection()
            await controller.is_init()
    except TimeoutError as err:
        await _async_shutdown(hass, data)
        raise ConfigEntryNotReady(
            f"No response from the AlarmDecoder within {INIT_TIMEOUT} seconds"
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AlarmDecoderConfigEntry
) -> None:
    """Unload a AlarmDecoder entry."""
    data = entry.runtime_data

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    await _async_shutdown(hass, data)


async def _async_shutdown(hass: HomeAssistant, data: AlarmDecoderData) -> None:
    """Stop reconnecting, remove listeners and close the connection."""
    data.shutdown = True
    data.restart = False
    if data.cancel_retry is not None:
        # A pending reconnect would otherwise revive this controller.
        data.cancel_retry()
        data.cancel_retry = None
    data.remove_update_listener()
    data.remove_stop_listener()
    if data.opening is not None and not data.opening.done():
        # close() can't interrupt a connect() in progress, which would then
        # leave the connection open. Close once the attempt finishes instead.
        data.opening.add_done_callback(
            lambda _: hass.async_add_executor_job(data.client.close)
        )
        return
    await hass.async_add_executor_job(data.client.close)


async def _update_listener(hass: HomeAssistant, entry: AlarmDecoderConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("AlarmDecoder options updated: %s", entry.as_dict()["options"])
    await hass.config_entries.async_reload(entry.entry_id)
