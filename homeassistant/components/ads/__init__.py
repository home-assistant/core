"""
ADS Component.

For more details about this component, please refer to the documentation.
https://home-assistant.io/components/ads/

"""
import os
import threading
import struct
import logging
import ctypes
from collections import namedtuple
import voluptuous as vol
from homeassistant.const import CONF_DEVICE, CONF_PORT, CONF_IP_ADDRESS, \
    EVENT_HOMEASSISTANT_STOP
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyads==2.2.6']

_LOGGER = logging.getLogger(__name__)

DATA_ADS = 'data_ads'

# Supported Types
ADSTYPE_INT = 'int'
ADSTYPE_UINT = 'uint'
ADSTYPE_BYTE = 'byte'
ADSTYPE_BOOL = 'bool'

DOMAIN = 'ads'

# config variable names
CONF_ADS_VAR = 'adsvar'
CONF_ADS_VAR_BRIGHTNESS = 'adsvar_brightness'
CONF_ADS_TYPE = 'adstype'
CONF_ADS_FACTOR = 'factor'
CONF_ADS_VALUE = 'value'

SERVICE_WRITE_DATA_BY_NAME = 'write_data_by_name'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Required(CONF_ADS_TYPE): vol.In([ADSTYPE_INT, ADSTYPE_UINT,
                                         ADSTYPE_BYTE]),
    vol.Required(CONF_ADS_VALUE): cv.match_all
})


def setup(hass, config):
    """Set up the ADS component."""
    import pyads
    conf = config[DOMAIN]

    # get ads connection parameters from config
    net_id = conf.get(CONF_DEVICE)
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf.get(CONF_PORT)

    # create a new ads connection
    client = pyads.Connection(net_id, port, ip_address)

    # add some constants to AdsHub
    AdsHub.ADS_TYPEMAP = {
        ADSTYPE_BOOL: pyads.PLCTYPE_BOOL,
        ADSTYPE_BYTE: pyads.PLCTYPE_BYTE,
        ADSTYPE_INT: pyads.PLCTYPE_INT,
        ADSTYPE_UINT: pyads.PLCTYPE_UINT,
    }

    AdsHub.PLCTYPE_BOOL = pyads.PLCTYPE_BOOL
    AdsHub.PLCTYPE_BYTE = pyads.PLCTYPE_BYTE
    AdsHub.PLCTYPE_INT = pyads.PLCTYPE_INT
    AdsHub.PLCTYPE_UINT = pyads.PLCTYPE_UINT
    AdsHub.ADSError = pyads.ADSError

    # connect to ads client and try to connect
    try:
        ads = AdsHub(client)
    except pyads.pyads.ADSError:
        _LOGGER.error(
            'Could not connect to ADS host (netid=%s, port=%s)', net_id, port
        )
        return False

    # add ads hub to hass data collection, listen to shutdown
    hass.data[DATA_ADS] = ads
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    def handle_write_data_by_name(call):
        """Write a value to the connected ADS device."""
        ads_var = call.data.get(CONF_ADS_VAR)
        ads_type = call.data.get(CONF_ADS_TYPE)
        value = call.data.get(CONF_ADS_VALUE)

        try:
            ads.write_by_name(ads_var, value, ads.ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    # load descriptions from services.yaml
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_WRITE_DATA_BY_NAME, handle_write_data_by_name,
        descriptions[SERVICE_WRITE_DATA_BY_NAME],
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME
    )

    return True


# tuple to hold data needed for notification
NotificationItem = namedtuple(
    'NotificationItem', 'hnotify huser name plc_datatype callback'
)


class AdsHub:
    """Representation of a PyADS connection."""

    def __init__(self, ads_client):
        """Initialize the ADS Hub."""
        self._client = ads_client
        self._client.open()

        # all ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""
        _LOGGER.debug('Shutting down ADS')
        for notification_item in self._notification_items.values():
            self._client.del_device_notification(
                notification_item.hnotify,
                notification_item.huser
            )
            _LOGGER.debug(
                'Deleting device notification %d, %d',
                notification_item.hnotify, notification_item.huser
            )
        self._client.close()

    def register_device(self, device):
        """Register a new device."""
        self._devices.append(device)

    def write_by_name(self, name, value, plc_datatype):
        """Write a value to the device."""
        with self._lock:
            return self._client.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        """Read a value from the device."""
        with self._lock:
            return self._client.read_by_name(name, plc_datatype)

    def add_device_notification(self, name, plc_datatype, callback):
        """Add a notification to the ADS devices."""
        from pyads import NotificationAttrib
        attr = NotificationAttrib(ctypes.sizeof(plc_datatype))

        with self._lock:
            hnotify, huser = self._client.add_device_notification(
                name, attr, self._device_notification_callback
            )
            hnotify = int(hnotify)

        _LOGGER.debug(
            'Added Device Notification %d for variable %s', hnotify, name
        )

        self._notification_items[hnotify] = NotificationItem(
            hnotify, huser, name, plc_datatype, callback
        )

    def _device_notification_callback(self, addr, notification, huser):
        """Handle device notifications."""
        contents = notification.contents

        hnotify = int(contents.hNotification)
        _LOGGER.debug('Received Notification %d', hnotify)
        data = contents.data

        try:
            notification_item = self._notification_items[hnotify]
        except KeyError:
            _LOGGER.debug('Unknown Device Notification handle: %d', hnotify)
            return

        # parse data to desired datatype
        if notification_item.plc_datatype == self.PLCTYPE_BOOL:
            value = bool(struct.unpack('<?', bytearray(data)[:1])[0])
        elif notification_item.plc_datatype == self.PLCTYPE_INT:
            value = struct.unpack('<h', bytearray(data)[:2])[0]
        elif notification_item.plc_datatype == self.PLCTYPE_BYTE:
            value = struct.unpack('<B', bytearray(data)[:1])[0]
        elif notification_item.plc_datatype == self.PLCTYPE_UINT:
            value = struct.unpack('<H', bytearray(data)[:2])[0]
        else:
            value = bytearray(data)
            _LOGGER.warning('No callback available for this datatype.')

        # execute callback
        notification_item.callback(notification_item.name, value)
