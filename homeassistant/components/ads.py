"""
ADS Component.

For more details about this component, please refer to the documentation.

"""
import logging
import voluptuous as vol
from homeassistant.const import CONF_DEVICE, CONF_PORT, CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv

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
    import pyads
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


class AdsHub:
    """ Representation of a PyADS connection. """

    def __init__(self, ads_client):
        self._client = ads_client
        self._client.open()

    def write_by_name(self, name, value, plc_datatype):
        return self._client.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        return self._client.read_by_name(name, plc_datatype)


class AdsDevice:

    def __init__(self):
        pass

    def write_by_name(self, name, value, plc_datatype):
        return ADS_HUB.write_by_name(name, value, plc_datatype)

    def read_by_name(self, name, plc_datatype):
        return ADS_HUB.read_by_name(name, plc_datatype)
