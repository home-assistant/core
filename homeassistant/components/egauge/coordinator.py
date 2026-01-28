"""Data update coordinator for eGauge energy monitors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from egauge_async.exceptions import (
    EgaugeAuthenticationError,
    EgaugeException,
    EgaugePermissionError,
)
from egauge_async.json.client import EgaugeJsonClient
from egauge_async.json.models import RegisterInfo
from httpx import ConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR_UPDATE_INTERVAL_SECONDS, DOMAIN, LOGGER

type EgaugeConfigEntry = ConfigEntry[EgaugeDataCoordinator]


@dataclass
class EgaugeData:
    """Data from eGauge device."""

    measurements: dict[str, float]  # Instantaneous values (W, V, A, etc.)
    counters: dict[str, float]  # Cumulative values (Ws)
    register_info: dict[str, RegisterInfo]  # Metadata for all registers


class EgaugeDataCoordinator(DataUpdateCoordinator[EgaugeData]):
    """Class to manage fetching eGauge data."""

    serial_number: str
    hostname: str

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL_SECONDS),
            config_entry=config_entry,
        )
        self.client = EgaugeJsonClient(
            host=config_entry.data[CONF_HOST],
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            client=get_async_client(
                hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL]
            ),
            use_ssl=config_entry.data[CONF_SSL],
        )
        # Populated in _async_setup
        self._register_info: dict[str, RegisterInfo] = {}

    async def _async_setup(self) -> None:
        try:
            self.serial_number = await self.client.get_device_serial_number()
            self.hostname = await self.client.get_hostname()
            self._register_info = await self.client.get_register_info()
        except (
            EgaugeAuthenticationError,
            EgaugePermissionError,
            EgaugeException,
        ) as err:
            # EgaugeAuthenticationError and EgaugePermissionError will raise ConfigEntryAuthFailed once reauth is implemented
            raise ConfigEntryError from err
        except ConnectError as err:
            raise UpdateFailed(f"Error fetching device info: {err}") from err

    async def _async_update_data(self) -> EgaugeData:
        """Fetch data from eGauge device."""
        try:
            measurements = await self.client.get_current_measurements()
            counters = await self.client.get_current_counters()
        except (
            EgaugeAuthenticationError,
            EgaugePermissionError,
            EgaugeException,
        ) as err:
            # will raise ConfigEntryAuthFailed once reauth is implemented
            raise ConfigEntryError("Error fetching device info: {err}") from err
        except ConnectError as err:
            raise UpdateFailed(f"Error fetching device info: {err}") from err

        return EgaugeData(
            measurements=measurements,
            counters=counters,
            register_info=self._register_info,
        )
