"""Support for APCUPSd via its Network Information Server (NIS)."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

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
PLATFORMS: Final = (Platform.BINARY_SENSOR, Platform.SENSOR)
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
    except OSError as ex:
        _LOGGER.error("Failure while testing APCUPSd status retrieval: %s", ex)
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

    def __init__(self, host: str, port: int) -> None:
        """Initialize the data object."""
        self._host = host
        self._port = port
        self.status: dict[str, Any] = {}

    @property
    def name(self) -> str | None:
        """Return the name of the UPS, if available."""
        return self.status.get("UPSNAME")

    @property
    def model(self) -> str | None:
        """Return the model of the UPS, if available."""
        # Different UPS models may report slightly different keys for model, here we
        # try them all.
        for model_key in ("APCMODEL", "MODEL"):
            if model_key in self.status:
                return self.status[model_key]
        return None

    @property
    def sw_version(self) -> str | None:
        """Return the software version of the APCUPSd, if available."""
        return self.status.get("VERSION")

    @property
    def hw_version(self) -> str | None:
        """Return the firmware version of the UPS, if available."""
        return self.status.get("FIRMWARE")

    @property
    def serial_no(self) -> str | None:
        """Return the unique serial number of the UPS, if available."""
        return self.status.get("SERIALNO")

    @property
    def statflag(self) -> str | None:
        """Return the STATFLAG indicating the status of the UPS, if available."""
        return self.status.get("STATFLAG")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Fetch the latest status from APCUPSd.

        Note that the result dict uses upper case for each resource, where our
        integration uses lower cases as keys internally.
        """
        self.status = status.parse(status.get(host=self._host, port=self._port))
