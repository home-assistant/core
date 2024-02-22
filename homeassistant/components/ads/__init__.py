"""Support for Automation Device Specification (ADS)."""
import asyncio
from asyncio import timeout
from collections import namedtuple
import ctypes
import logging
import struct
import threading

import pyads
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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var = call.data[CONF_ADS_VAR]
        ads_type = call.data[CONF_ADS_TYPE]
        value = call.data[CONF_ADS_VALUE]

        try:
            ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    hass.services.register(
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


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client):
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()

        # All ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
        for notification_item in self._notification_items.values():
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
        try:
            self._client.close()
        except pyads.ADSError as err:
            _LOGGER.error(err)

    def register_device(self, device):
        """Register a new device."""
        self._devices.append(device)

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


class AdsEntity(Entity):
    """Representation of ADS entity."""

    _attr_should_poll = False

    def __init__(self, ads_hub, name, ads_var):
        """Initialize ADS binary sensor."""
        self._state_dict = {}
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
