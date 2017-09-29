"""
ADS Component.

For more details about this component, please refer to the documentation.

"""
import struct
import logging
import ctypes
from collections import namedtuple
import voluptuous as vol
from homeassistant.const import CONF_DEVICE, CONF_PORT, CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv
import pyads
from pyads import PLCTYPE_BOOL, PLCTYPE_INT, PLCTYPE_UINT, PLCTYPE_BYTE

REQUIREMENTS = ['pyads']

_LOGGER = logging.getLogger(__name__)

DATA_ADS = 'data_ads'
ADS_PLATFORMS = ['switch', 'binary_sensor', 'light']
DOMAIN = 'ads'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """ Set up the ADS component. """
    _LOGGER.info('created ADS client')
    conf = config[DOMAIN]

    net_id = conf.get(CONF_DEVICE)
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf.get(CONF_PORT)

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ads = AdsHub(client)
    except pyads.pyads.ADSError as e:
        _LOGGER.error('Could not connect to ADS host (netid={}, port={})'
                      .format(net_id, port))
        return False

    hass.data[DATA_ADS] = ads

    return True


NotificationItem = namedtuple(
    'NotificationItem', 'hnotify huser name plc_datatype callback'
)


class AdsHub:
    """ Representation of a PyADS connection. """

    def __init__(self, ads_client):
        self._client = ads_client
        self._client.open()

        # all ADS devices are registered here
        self._devices = []
        self._notification_items = {}

    def register_device(self, device):
        """ Register a new device. """
        self._devices.append(device)

    def write_by_name(self, name, value, plc_datatype):
        return self._client.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        return self._client.read_by_name(name, plc_datatype)

    def add_device_notification(self, name, plc_datatype, callback):
        """ Add a notification to the ADS devices. """
        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))
        hnotify, huser = self._client.add_device_notification(
            name, attr, self._device_notification_callback
        )
        hnotify = int(hnotify)

        _LOGGER.debug('Added Device Notification {0}'.format(hnotify))

        self._notification_items[hnotify] = NotificationItem(
            hnotify, huser, name, plc_datatype, callback
        )

    def _device_notification_callback(self, addr, notification, huser):
        contents = notification.contents

        hnotify = int(contents.hNotification)
        _LOGGER.debug('Received Notification {0}'.format(hnotify))
        data = contents.data

        try:
            notification_item = self._notification_items[hnotify]
        except KeyError:
            _LOGGER.debug('Unknown Device Notification handle: {0}'
                          .format(hnotify))
            return

        # parse data to desired datatype
        if notification_item.plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack('<?', bytearray(data)[:1])[0])
        else:
            _LOGGER.warning('No callback available for this datatype.')

        # execute callback
        notification_item.callback(notification_item.name, value)
