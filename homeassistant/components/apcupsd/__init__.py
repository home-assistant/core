"""Support for APCUPSd via its Network Information Server (NIS)."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

from apcaccess import status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "apcupsd"
VALUE_ONLINE: Final = 8
PLATFORMS: Final = (Platform.BINARY_SENSOR, Platform.SENSOR)
MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=60)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


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
        self.status: dict[str, str] = {}

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
    def serial_no(self) -> str | None:
        """Return the unique serial number of the UPS, if available."""
        return self.status.get("SERIALNO")

    @property
    def statflag(self) -> str | None:
        """Return the STATFLAG indicating the status of the UPS, if available."""
        return self.status.get("STATFLAG")

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the DeviceInfo of this APC UPS for the sensors, if serial number is available."""
        if self.serial_no is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self.serial_no)},
            model=self.model,
            manufacturer="APC",
            name=self.name if self.name is not None else "APC UPS",
            hw_version=self.status.get("FIRMWARE"),
            sw_version=self.status.get("VERSION"),
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs: Any) -> None:
        """Fetch the latest status from APCUPSd.

        Note that the result dict uses upper case for each resource, where our
        integration uses lower cases as keys internally.
        """
        self.status = status.parse(status.get(host=self._host, port=self._port))
