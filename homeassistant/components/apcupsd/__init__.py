"""Support for APCUPSd via its Network Information Server (NIS)."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from apcaccess import status
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "apcupsd"
VALUE_ONLINE: Final = 8
PLATFORMS: Final = (Platform.SENSOR, Platform.BINARY_SENSOR)
MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=60)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default="localhost"): cv.string,
                vol.Optional(CONF_PORT, default=3551): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration from legacy YAML configurations."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    # We only import configs from YAML if it hasn't been imported. If there is a config
    # entry marked with SOURCE_IMPORT, it means the YAML config has been imported.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return True

    # Since the YAML configuration for apcupsd consists of two parts:
    # apcupsd:
    #   host: xxx
    #   port: xxx
    # sensor:
    #   - platform: apcupsd
    #     resource:
    #       - resource_1
    #       - resource_2
    #       - ...
    # Here at the integration set up we do not have the entire information to be
    # imported to config flow yet. So we temporarily store the configuration to
    # hass.data[DOMAIN] under a special entry_id SOURCE_IMPORT (which shouldn't
    # conflict with other entry ids). Later when the sensor platform setup is
    # called we gather the resources information and from there we start the
    # actual config entry imports.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SOURCE_IMPORT] = conf
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Use config values to set up a function enabling status retrieval."""
    data_service = APCUPSdData(
        config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
    )

    try:
        await hass.async_add_executor_job(data_service.update)
    # It doesn't really matter why we're not able to get the status, just that we can't.
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception("Failure while testing APCUPSd status retrieval", exc_info=ex)
        return False

    # Store the data service object.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = data_service

    # Forward the config entries to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class APCUPSdData:
    """Stores the data retrieved from APCUPSd.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._status = None

    @property
    def status(self) -> dict[str, str] | None:
        """Return the status dict.

        Note that the result dict uses upper case for each resource, where our
        integration uses lower cases as keys internally.
        """
        return self._status

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Fetch the latest status from APCUPSd."""
        self._status = status.parse(status.get(host=self._host, port=self._port))
