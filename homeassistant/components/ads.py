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
from pyads import PLCTYPE_BOOL

REQUIREMENTS = ['pyads==2.2.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ads'

ADS_HUB = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """ Set up the ADS component. """
    global ADS_HUB

    _LOGGER.info('created ADS client')
    conf = config[DOMAIN]

    net_id = conf.get(CONF_DEVICE)
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf.get(CONF_PORT)

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ADS_HUB = AdsHub(client)
    except pyads.pyads.ADSError as e:
        _LOGGER.error('Could not connect to ADS host (netid={}, port={})'
                      .format(net_id, port))
        return False

    return True


NotificationItem = namedtuple(
    'NotificationItem', 'hnotify huser device name plc_datatype callback'
)


class AdsHub:
    """ Representation of a PyADS connection. """

    def __init__(self, ads_client):
        self.__client = ads_client
        self.__client.open()

        # all ADS devices are registered here
        self.__devices = []
        self._notification_items = {}

    def register_device(self, device):
        """ Register a new device. """
        self.__devices.append(device)

    def write_by_name(self, name, value, plc_datatype):
        return self.__client.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        return self.__client.read_by_name(name, plc_datatype)

    def add_device_notification(self, device, name, plc_datatype, callback):
        """ Add a notification to the ADS devices. """
        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))
        hnotify, huser = self.__client.add_device_notification(
            name, attr, self.device_notification_callback
        )

        self._notification_items[hnotify] = NotificationItem(
            hnotify, huser, device, name, plc_datatype, callback
        )

    def device_notification_callback(self, addr, notification, huser):
        contents = notification.contents

        hnotify = contents.hNotification
        data = contents.data

        try:
            notification_item = self._notification_items[hnotify]
        except KeyError:
            _LOGGER.warning('Received notification with unknown handle.')
            return

        # parse data to desired datatype
        if notification_item.plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack(bytearray(data)[:1])[0])
        else:
            return

        # execute callback
        notification_item.callback(notification_item.name, value)


class AdsDevice:

    def __init__(self):
        self.__hub = ADS_HUB
        self.__hub.register_device(self)

    def write_by_name(self, name, value, plc_datatype):
        return self.__hub.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        return self.__hub.read_by_name(name, plc_datatype)

    def add_bool_device_notification(self, name, callback):
        self.__hub.add_device_notification(
            self, name, pyads.PLCTYPE_BOOL, callback
        )
