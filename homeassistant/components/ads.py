"""
ADS Component.

For more details about this component, please refer to the documentation.
https://home-assistant.io/components/ads/

"""
import threading
import struct
import logging
import ctypes
from collections import namedtuple
import voluptuous as vol
from homeassistant.const import CONF_DEVICE, CONF_PORT, CONF_IP_ADDRESS, \
    EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyads==2.2.6']

_LOGGER = logging.getLogger(__name__)

DATA_ADS = 'data_ads'

# Supported Types
ADSTYPE_INT = 'int'
ADSTYPE_UINT = 'uint'
ADSTYPE_BYTE = 'byte'
ADSTYPE_BOOL = 'bool'


ADS_PLATFORMS = ['switch', 'binary_sensor', 'light']
DOMAIN = 'ads'

# config variable names
CONF_ADSVAR = 'adsvar'
CONF_ADSTYPE = 'adstype'
CONF_ADS_USE_NOTIFY = 'use_notify'
CONF_ADS_POLL_INTERVAL = 'poll_interval'
CONF_ADS_FACTOR = 'factor'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_ADS_POLL_INTERVAL, default=1000): cv.positive_int,
        vol.Optional(CONF_ADS_USE_NOTIFY, default=True): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ADS component."""
    import pyads
    conf = config[DOMAIN]

    # get ads connection parameters from config
    net_id = conf.get(CONF_DEVICE)
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf.get(CONF_PORT)
    poll_interval = conf.get(CONF_ADS_POLL_INTERVAL)
    use_notify = conf.get(CONF_ADS_USE_NOTIFY)

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
        ads = AdsHub(client, poll_interval=poll_interval,
                     use_notify=use_notify)
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
        adsvar = call.data.get('adsvar')
        adstype = call.data.get('adstype')
        value = call.data.get('value')

        assert adstype in ads.ADS_TYPEMAP

        try:
            ads.write_by_name(adsvar, value, ads.ADS_TYPEMAP[adstype])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    hass.services.register(DOMAIN, 'write_data_by_name',
                           handle_write_data_by_name)

    return True


# tuple to hold data needed for notification
NotificationItem = namedtuple(
    'NotificationItem', 'hnotify huser name plc_datatype callback'
)


class AdsHub:
    """Representation of a PyADS connection."""

    def __init__(self, ads_client, poll_interval, use_notify):
        self.poll_interval = poll_interval
        self.use_notify = use_notify

        self._client = ads_client
        self._client.open()

        # all ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""
        _LOGGER.debug('Shutting down ADS')
        for _, notification_item in self._notification_items.items():
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
        """Callback for device notifications."""
        from pyads import PLCTYPE_BOOL, PLCTYPE_INT, PLCTYPE_BYTE, PLCTYPE_UINT
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
        if notification_item.plc_datatype == PLCTYPE_BOOL:
            value = bool(struct.unpack('<?', bytearray(data)[:1])[0])
        elif notification_item.plc_datatype == PLCTYPE_INT:
            value = struct.unpack('<h', bytearray(data)[:2])[0]
        elif notification_item.plc_datatype == PLCTYPE_BYTE:
            value = struct.unpack('<B', bytearray(data)[:1])[0]
        elif notification_item.plc_datatype == PLCTYPE_UINT:
            value = struct.unpack('<H', bytearray(data)[:2])[0]
        else:
            value = bytearray(data)
            _LOGGER.warning('No callback available for this datatype.')

        # execute callback
        notification_item.callback(notification_item.name, value)
