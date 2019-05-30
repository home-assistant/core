"""Support for IOTA wallets."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_IRI = 'iri'
CONF_TESTNET = 'testnet'
CONF_WALLET_NAME = 'name'
CONF_WALLET_SEED = 'seed'
CONF_WALLETS = 'wallets'

DOMAIN = 'iota'

IOTA_PLATFORMS = ['sensor']

SCAN_INTERVAL = timedelta(minutes=10)

WALLET_CONFIG = vol.Schema({
    vol.Required(CONF_WALLET_NAME): cv.string,
    vol.Required(CONF_WALLET_SEED): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_IRI): cv.string,
        vol.Optional(CONF_TESTNET, default=False): cv.boolean,
        vol.Required(CONF_WALLETS): vol.All(cv.ensure_list, [WALLET_CONFIG]),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the IOTA component."""
    iota_config = config[DOMAIN]

    for platform in IOTA_PLATFORMS:
        load_platform(hass, platform, DOMAIN, iota_config, config)

    return True


class IotaDevice(Entity):
    """Representation of a IOTA device."""

    def __init__(self, name, seed, iri, is_testnet=False):
        """Initialise the IOTA device."""
        self._name = name
        self._seed = seed
        self.iri = iri
        self.is_testnet = is_testnet

    @property
    def name(self):
        """Return the default name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {CONF_WALLET_NAME: self._name}
        return attr

    @property
    def api(self):
        """Construct API object for interaction with the IRI node."""
        from iota import Iota
        return Iota(adapter=self.iri, seed=self._seed)
