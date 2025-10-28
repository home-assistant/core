"""Data update coordinator for eGauge energy monitors."""

from __future__ import annotations

from datetime import timedelta

from egauge_async.json.client import (
    EgaugeAuthenticationError,
    EgaugeJsonClient,
    EgaugeParsingException,
)
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
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER
from .models import EgaugeData
from .util import _build_client_url

type EgaugeConfigEntry = ConfigEntry[EgaugeDataCoordinator]


class EgaugeDataCoordinator(DataUpdateCoordinator[EgaugeData]):
    """Class to manage fetching eGauge data."""

    serial_number: str
    hostname: str

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            config_entry=config_entry,
        )
        self.client = EgaugeJsonClient(
            base_url=_build_client_url(
                config_entry.data[CONF_HOST], config_entry.data[CONF_SSL]
            ),
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            client=get_async_client(
                hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL]
            ),
        )
        # Populated on first refresh
        self._register_info: dict[str, RegisterInfo] = {}

    async def _async_update_data(self) -> EgaugeData:
        """Fetch data from eGauge device."""
        # First time only: fetch static device info
        if self._register_info is None:
            try:
                self.serial_number = await self.client.get_device_serial_number()
                self.hostname = await self.client.get_hostname()
                self._register_info = await self.client.get_register_info()
            except EgaugeAuthenticationError as err:
                raise ConfigEntryAuthFailed from err
            except (ConnectError, EgaugeParsingException) as err:
                raise UpdateFailed(f"Error fetching device info: {err}") from err

        # Every time: fetch dynamic measurements
        try:
            measurements = await self.client.get_current_measurements()
            counters = await self.client.get_current_counters()
        except EgaugeAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (ConnectError, EgaugeParsingException) as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return EgaugeData(
            measurements=measurements,
            counters=counters,
            register_info=self._register_info,
        )
