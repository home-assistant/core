"""Support for AlarmDecoder devices."""
from datetime import timedelta
import logging

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_DEVICE_BAUD,
    CONF_DEVICE_PATH,
    DATA_AD,
    DATA_REMOVE_STOP_LISTENER,
    DATA_REMOVE_UPDATE_LISTENER,
    DATA_RESTART,
    DOMAIN,
    PROTOCOL_SERIAL,
    PROTOCOL_SOCKET,
    SIGNAL_PANEL_MESSAGE,
    SIGNAL_REL_MESSAGE,
    SIGNAL_RFX_MESSAGE,
    SIGNAL_ZONE_FAULT,
    SIGNAL_ZONE_RESTORE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AlarmDecoder config flow."""
    undo_listener = entry.add_update_listener(_update_listener)

    ad_connection = entry.data
    protocol = ad_connection[CONF_PROTOCOL]

    def stop_alarmdecoder(event):
        """Handle the shutdown of AlarmDecoder."""
        if not hass.data.get(DOMAIN):
            return
        _LOGGER.debug("Shutting down alarmdecoder")
        hass.data[DOMAIN][entry.entry_id][DATA_RESTART] = False
        controller.close()

    async def open_connection(now=None):
        """Open a connection to AlarmDecoder."""
        try:
            await hass.async_add_executor_job(controller.open, baud)
        except NoDeviceError:
            _LOGGER.debug("Failed to connect. Retrying in 5 seconds")
            async_call_later(hass, timedelta(seconds=5), open_connection)
            return
        _LOGGER.debug("Established a connection with the alarmdecoder")
        hass.data[DOMAIN][entry.entry_id][DATA_RESTART] = True

    def handle_closed_connection(event):
        """Restart after unexpected loss of connection."""
        if not hass.data[DOMAIN][entry.entry_id][DATA_RESTART]:
            return
        hass.data[DOMAIN][entry.entry_id][DATA_RESTART] = False
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_AD: controller,
        DATA_REMOVE_UPDATE_LISTENER: undo_listener,
        DATA_REMOVE_STOP_LISTENER: remove_stop_listener,
        DATA_RESTART: False,
    }

    await open_connection()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a AlarmDecoder entry."""
    hass.data[DOMAIN][entry.entry_id][DATA_RESTART] = False

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not unload_ok:
        return False

    hass.data[DOMAIN][entry.entry_id][DATA_REMOVE_UPDATE_LISTENER]()
    hass.data[DOMAIN][entry.entry_id][DATA_REMOVE_STOP_LISTENER]()
    await hass.async_add_executor_job(hass.data[DOMAIN][entry.entry_id][DATA_AD].close)

    if hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("AlarmDecoder options updated: %s", entry.as_dict()["options"])
    await hass.config_entries.async_reload(entry.entry_id)
