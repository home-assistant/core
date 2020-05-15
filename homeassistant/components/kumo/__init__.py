"""Support for Mitsubishi KumoCloud devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util.json import load_json, save_json

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["pykumo==0.1.5"]
DOMAIN = "kumo"
KUMO_DATA = "kumo_data"
KUMO_CONFIG_CACHE = "kumo_cache.json"
CONF_PREFER_CACHE = "prefer_cache"
CONF_CONNECT_TIMEOUT = "connect_timeout"
CONF_RESPONSE_TIMEOUT = "response_timeout"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PREFER_CACHE, default=False): cv.boolean,
                vol.Optional(CONF_CONNECT_TIMEOUT): float,
                vol.Optional(CONF_RESPONSE_TIMEOUT): float,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class KumoData:
    """Hold object representing KumoCloud account."""

    def __init__(self, account, domain_config):
        """Init KumoCloudAccount object."""
        self._account = account
        self._domain_config = domain_config

    def get_account(self):
        """Retrieve account."""
        return self._account

    def get_domain_config(self):
        """Retrieve domain config."""
        return self._domain_config

    def get_raw_json(self):
        """Retrieve raw JSON config from account."""
        return self._account.get_raw_json()


def setup_kumo(hass, config):
    """Set up the Kumo indoor units."""
    hass.async_create_task(async_load_platform(hass, "climate", DOMAIN, {}, config))


async def async_setup(hass, config):
    """Set up the Kumo Cloud devices. Will create climate and sensor components to support devices listed on the provided Kumo Cloud account."""

    # pylint: disable=C0415
    import pykumo

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    prefer_cache = config[DOMAIN].get(CONF_PREFER_CACHE)

    # Read config from either remote KumoCloud server or
    # cached JSON.
    cached_json = {}
    success = False
    if prefer_cache:
        # Try to load from cache
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE)
        ) or {"fetched": False}
        account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
    else:
        # Try to load from server
        account = pykumo.KumoCloudAccount(username, password)
    if account.try_setup():
        if prefer_cache:
            _LOGGER.info("Loaded config from local cache")
            success = True
        else:
            await hass.async_add_executor_job(
                save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
            )
            _LOGGER.info("Loaded config from KumoCloud server")
            success = True
    else:
        # Fall back
        if prefer_cache:
            # Try to load from server
            account = pykumo.KumoCloudAccount(username, password)
        else:
            # Try to load from cache
            cached_json = await hass.async_add_executor_job(
                load_json, hass.config.path(KUMO_CONFIG_CACHE)
            ) or {"fetched": False}
            account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
        if account.try_setup():
            if prefer_cache:
                await hass.async_add_executor_job(
                    save_json,
                    hass.config.path(KUMO_CONFIG_CACHE),
                    account.get_raw_json(),
                )
                _LOGGER.info("Loaded config from KumoCloud server as fallback")
                success = True
            else:
                _LOGGER.info("Loaded config from local cache as fallback")
                success = True

    if success:
        hass.data[KUMO_DATA] = KumoData(account, config[DOMAIN])
        setup_kumo(hass, config)
        return True

    _LOGGER.warning("Could not load config from KumoCloud server or cache")
    return False
