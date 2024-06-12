"""Support for Automation Device Specification (ADS)."""

import asyncio
from asyncio import timeout
from collections import namedtuple
import ctypes
from enum import Enum
import logging
import struct
import threading
from typing import Any

import pyads
import pyads.errorcodes
import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DATA_ADS = "data_ads"

# Supported Types
ADSTYPE_BOOL = "bool"
ADSTYPE_BYTE = "byte"
ADSTYPE_DINT = "dint"
ADSTYPE_INT = "int"
ADSTYPE_UDINT = "udint"
ADSTYPE_UINT = "uint"

ADS_TYPEMAP = {
    ADSTYPE_BOOL: pyads.PLCTYPE_BOOL,
    ADSTYPE_BYTE: pyads.PLCTYPE_BYTE,
    ADSTYPE_DINT: pyads.PLCTYPE_DINT,
    ADSTYPE_INT: pyads.PLCTYPE_INT,
    ADSTYPE_UDINT: pyads.PLCTYPE_UDINT,
    ADSTYPE_UINT: pyads.PLCTYPE_UINT,
}

CONF_ADS_FACTOR = "factor"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VALUE = "value"
CONF_ADS_VAR = "adsvar"
CONF_ADS_VAR_BRIGHTNESS = "adsvar_brightness"
CONF_ADS_VAR_POSITION = "adsvar_position"

STATE_KEY_STATE = "state"
STATE_KEY_BRIGHTNESS = "brightness"
STATE_KEY_POSITION = "position"

DOMAIN = "ads"

SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema(
    {
        vol.Required(CONF_ADS_TYPE): vol.In(
            [
                ADSTYPE_INT,
                ADSTYPE_UINT,
                ADSTYPE_BYTE,
                ADSTYPE_BOOL,
                ADSTYPE_DINT,
                ADSTYPE_UDINT,
            ]
        ),
        vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
        vol.Required(CONF_ADS_VAR): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""

    conf = config[DOMAIN]

    net_id = conf[CONF_DEVICE]
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf[CONF_PORT]

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ads = AdsHub(client)
    except pyads.ADSError:
        _LOGGER.error(
            "Could not connect to ADS host (netid=%s, ip=%s, port=%s)",
            net_id,
            ip_address,
            port,
        )
        return False

    hass.data[DATA_ADS] = ads
    hass.async_create_background_task(ads.heartbeat(), "heartbeat")
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var = call.data[CONF_ADS_VAR]
        ads_type = call.data[CONF_ADS_TYPE]
        value = call.data[CONF_ADS_VALUE]

        try:
            ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )

    return True


# Tuple to hold data needed for notification
NotificationItem = namedtuple(
    "NotificationItem", "hnotify huser name plc_datatype callback"
)

# Tuple to hold data needed to restore notification
DeletedNotification = namedtuple("DeletedNotification", "name plc_datatype callback")


class ConnectionState(Enum):
    """Reresentation of ADS connection state."""

    Connected = 1
    ReadyToReconnect = 2
    Disconnected = 3


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client: pyads.Connection) -> None:
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()
        self._is_running = True

        # All ADS devices are registered here
        self._notification_items: dict[int, NotificationItem] = {}
        self._lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")

        self._is_running = False
        self._delete_device_notifications()

        try:
            self._client.close()
        except pyads.ADSError as err:
            _LOGGER.error(err)

    def write_by_name(self, name, value, plc_datatype):
        """Write a value to the device."""

        with self._lock:
            try:
                return self._client.write_by_name(name, value, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error writing %s: %s", name, err)

    def read_by_name(self, name, plc_datatype):
        """Read a value from the device."""

        with self._lock:
            try:
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error reading %s: %s", name, err)

    def add_device_notification(self, name, plc_datatype, callback):
        """Add a notification to the ADS devices."""

        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))

        with self._lock:
            try:
                hnotify, huser = self._client.add_device_notification(
                    name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("Error subscribing to %s: %s", name, err)
            else:
                hnotify = int(hnotify)
                self._notification_items[hnotify] = NotificationItem(
                    hnotify, huser, name, plc_datatype, callback
                )

                _LOGGER.debug(
                    "Added device notification %d for variable %s", hnotify, name
                )

    async def heartbeat(
        self,
        heartbeat_interval: float = 5.0,
        max_wait_time: float = 120.0,
        communication_timeout_while_disconnected_ms: int = 100,
    ):
        """Periodically checks and handles the connection state of the client.

        Adjusts the wait time and communication timeout based on the connection state, with exponential backoff when disconnected.

        Attempts reconnection and manages device notifications upon reconnection.
        """
        deleted_device_notifications: list[DeletedNotification] = []

        default_timeout_ms = 5000

        wait_time = heartbeat_interval

        while self._is_running:
            connection_state = self._check_connection()
            if connection_state == ConnectionState.Connected:
                if wait_time != heartbeat_interval:
                    _LOGGER.info("Reconnected")
                    self._client.set_timeout(ms=default_timeout_ms)
                    wait_time = heartbeat_interval

                await asyncio.sleep(wait_time)
            elif connection_state == ConnectionState.Disconnected:
                if wait_time == heartbeat_interval:
                    _LOGGER.info("Disconnected, waiting for device availability")
                    self._client.set_timeout(
                        ms=communication_timeout_while_disconnected_ms
                    )

                wait_time = (
                    wait_time * 2 if wait_time * 2 < max_wait_time else max_wait_time
                )
                _LOGGER.debug("Waiting %d seconds to check device state", wait_time)
                await asyncio.sleep(wait_time)
            elif connection_state == ConnectionState.ReadyToReconnect:
                if not deleted_device_notifications:
                    deleted_device_notifications = self._delete_device_notifications()

                self._reconnect()

                while deleted_device_notifications:
                    self.add_device_notification(*deleted_device_notifications.pop())

    def _check_connection(self) -> ConnectionState:
        try:
            self._client.read_state()
        except pyads.ADSError as read_state_error:
            if read_state_error.err_code not in pyads.errorcodes.ERROR_CODES:
                return ConnectionState.ReadyToReconnect
            return ConnectionState.Disconnected
        else:
            return ConnectionState.Connected

    def _reconnect(self):
        try:
            self._client.close()
            self._client.open()
        except pyads.ADSError as reconnect_error:
            _LOGGER.error(reconnect_error)
            return

    def _device_notification_callback(self, notification, name):
        """Handle device notifications."""
        contents = notification.contents

        hnotify = int(contents.hNotification)
        _LOGGER.debug("Received notification %d", hnotify)

        # get dynamically sized data array
        data_size = contents.cbSampleSize
        data = (ctypes.c_ubyte * data_size).from_address(
            ctypes.addressof(contents)
            + pyads.structs.SAdsNotificationHeader.data.offset
        )

        try:
            with self._lock:
                notification_item = self._notification_items[hnotify]
        except KeyError:
            _LOGGER.error("Unknown device notification handle: %d", hnotify)
            return

        # Parse data to desired datatype
        if notification_item.plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack("<?", bytearray(data))[0])
        elif notification_item.plc_datatype == pyads.PLCTYPE_INT:
            value = struct.unpack("<h", bytearray(data))[0]
        elif notification_item.plc_datatype == pyads.PLCTYPE_BYTE:
            value = struct.unpack("<B", bytearray(data))[0]
        elif notification_item.plc_datatype == pyads.PLCTYPE_UINT:
            value = struct.unpack("<H", bytearray(data))[0]
        elif notification_item.plc_datatype == pyads.PLCTYPE_DINT:
            value = struct.unpack("<i", bytearray(data))[0]
        elif notification_item.plc_datatype == pyads.PLCTYPE_UDINT:
            value = struct.unpack("<I", bytearray(data))[0]
        else:
            value = bytearray(data)
            _LOGGER.warning("No callback available for this datatype")

        notification_item.callback(notification_item.name, value)

    def _delete_device_notifications(self) -> list[DeletedNotification]:
        result = [
            DeletedNotification(item.name, item.plc_datatype, item.callback)
            for item in self._notification_items.values()
        ]

        while self._notification_items:
            _, notification_item = self._notification_items.popitem()
            _LOGGER.debug(
                "Deleting device notification %d, %d",
                notification_item.hnotify,
                notification_item.huser,
            )
            try:
                self._client.del_device_notification(
                    notification_item.hnotify, notification_item.huser
                )
            except pyads.ADSError as err:
                _LOGGER.error(err)

        return result


class AdsEntity(Entity):
    """Representation of ADS entity."""

    _attr_should_poll = False

    def __init__(self, ads_hub, name, ads_var) -> None:
        """Initialize ADS binary sensor."""
        self._state_dict: dict[str, Any] = {}
        self._state_dict[STATE_KEY_STATE] = None
        self._ads_hub = ads_hub
        self._ads_var = ads_var
        self._event = None
        self._attr_unique_id = ads_var
        self._attr_name = name

    async def async_initialize_device(
        self, ads_var, plctype, state_key=STATE_KEY_STATE, factor=None
    ):
        """Register device notification."""

        def update(name, value):
            """Handle device notifications."""
            _LOGGER.debug("Variable %s changed its value to %d", name, value)

            if factor is None:
                self._state_dict[state_key] = value
            else:
                self._state_dict[state_key] = value / factor

            asyncio.run_coroutine_threadsafe(async_event_set(), self.hass.loop)
            self.schedule_update_ha_state()

        async def async_event_set():
            """Set event in async context."""
            self._event.set()

        self._event = asyncio.Event()

        await self.hass.async_add_executor_job(
            self._ads_hub.add_device_notification, ads_var, plctype, update
        )
        try:
            async with timeout(10):
                await self._event.wait()
        except TimeoutError:
            _LOGGER.debug("Variable %s: Timeout during first update", ads_var)

    @property
    def available(self) -> bool:
        """Return False if state has not been updated yet."""
        return self._state_dict[STATE_KEY_STATE] is not None
