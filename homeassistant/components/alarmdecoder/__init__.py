"""Support for AlarmDecoder devices."""

import asyncio
from dataclasses import dataclass, field
import logging
import threading

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
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
RECONNECT_DELAY = 5
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
    restart: bool = False
    closed: bool = False
    connecting: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AlarmDecoderConfigEntry
) -> None:
    """Set up AlarmDecoder config flow."""
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    ad_connection = entry.data
    protocol = ad_connection[CONF_PROTOCOL]

    def stop_alarmdecoder(event):
        """Handle the shutdown of AlarmDecoder."""
        _LOGGER.debug("Shutting down alarmdecoder")
        close_controller()

    def open_controller() -> None:
        """Connect, unless already closed, and honor a close that came meanwhile."""
        with data.lock:
            if data.closed:
                return
            data.connecting = True
        try:
            controller.open(baud)
        finally:
            with data.lock:
                data.connecting = False
                closed = data.closed
            if closed:
                controller.close()
        data.restart = True

    def close_controller() -> None:
        """Close the connection once, or leave that to a connect in progress."""
        with data.lock:
            if data.closed:
                return
            data.closed = True
            # close() can't interrupt connect(), which would then leave the
            # connection open, so open_controller() closes when it finishes.
            if data.connecting:
                return
        controller.close()

    async def async_close_controller() -> None:
        """Close the connection without blocking the event loop."""
        await hass.async_add_executor_job(close_controller)

    async def async_reconnect() -> None:
        """Try to reconnect until it works; unloading the entry cancels this."""
        while True:
            try:
                await hass.async_add_executor_job(open_controller)
            except NoDeviceError:
                _LOGGER.debug(
                    "Failed to connect. Retrying in %s seconds", RECONNECT_DELAY
                )
                await asyncio.sleep(RECONNECT_DELAY)
            else:
                _LOGGER.debug("Established a connection with the alarmdecoder")
                return

    @callback
    def start_reconnect() -> None:
        """Reconnect in the background, so that it can't hold up startup."""
        entry.async_create_background_task(
            hass, async_reconnect(), "alarmdecoder reconnect"
        )

    def handle_closed_connection(event):
        """Restart after unexpected loss of connection."""
        if data.closed or not data.restart:
            return
        data.restart = False
        _LOGGER.warning("AlarmDecoder unexpectedly lost connection")
        hass.add_job(start_reconnect)

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

    data = entry.runtime_data = AlarmDecoderData(controller)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_alarmdecoder)
    )
    entry.async_on_unload(async_close_controller)

    try:
        async with asyncio.timeout(INIT_TIMEOUT):
            await hass.async_add_executor_job(open_controller)
            await controller.is_init()
    except NoDeviceError as err:
        raise ConfigEntryNotReady(f"Can't connect to the AlarmDecoder: {err}") from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"No response from the AlarmDecoder within {INIT_TIMEOUT} seconds"
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AlarmDecoderConfigEntry
) -> None:
    """Unload a AlarmDecoder entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def _update_listener(hass: HomeAssistant, entry: AlarmDecoderConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("AlarmDecoder options updated: %s", entry.as_dict()["options"])
    await hass.config_entries.async_reload(entry.entry_id)
