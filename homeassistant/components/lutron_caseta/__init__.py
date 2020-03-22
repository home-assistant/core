"""Component for interacting with a Lutron Caseta system."""
import logging

from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

LUTRON_CASETA_SMARTBRIDGE = "lutron_smartbridge"

DOMAIN = "lutron_caseta"

CONF_KEYFILE = "keyfile"
CONF_CERTFILE = "certfile"
CONF_CA_CERTS = "ca_certs"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_KEYFILE): cv.string,
                vol.Required(CONF_CERTFILE): cv.string,
                vol.Required(CONF_CA_CERTS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

LUTRON_CASETA_COMPONENTS = ["light", "switch", "cover", "scene", "fan"]


async def async_setup(hass, base_config):
    """Set up the Lutron component."""

    config = base_config.get(DOMAIN)
    keyfile = hass.config.path(config[CONF_KEYFILE])
    certfile = hass.config.path(config[CONF_CERTFILE])
    ca_certs = hass.config.path(config[CONF_CA_CERTS])
    bridge = Smartbridge.create_tls(
        hostname=config[CONF_HOST],
        keyfile=keyfile,
        certfile=certfile,
        ca_certs=ca_certs,
    )
    hass.data[LUTRON_CASETA_SMARTBRIDGE] = bridge
    await bridge.connect()
    if not hass.data[LUTRON_CASETA_SMARTBRIDGE].is_connected():
        _LOGGER.error(
            "Unable to connect to Lutron smartbridge at %s", config[CONF_HOST]
        )
        return False

    _LOGGER.info("Connected to Lutron smartbridge at %s", config[CONF_HOST])

    for component in LUTRON_CASETA_COMPONENTS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config)
        )

    return True


class LutronCasetaDevice(Entity):
    """Common base class for all Lutron Caseta devices."""

    def __init__(self, device, bridge):
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        """
        self._device = device
        self._smartbridge = bridge

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_subscriber(self.device_id, self.async_write_ha_state)

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._device["name"]

    @property
    def serial(self):
        """Return the serial number of the device."""
        return self._device["serial"]

    @property
    def unique_id(self):
        """Return the unique ID of the device (serial)."""
        return str(self.serial)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {"device_id": self.device_id, "zone_id": self._device["zone"]}
        return attr

    @property
    def should_poll(self):
        """No polling needed."""
        return False
