"""Code to handle the Plenticore API."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
from typing import Dict, Union

from aiohttp.client_exceptions import ClientError
from kostal.plenticore import PlenticoreApiClient, PlenticoreAuthenticationException

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Plenticore:
    """Manages the Plenticore API."""

    def __init__(self, hass, config_entry):
        """Create a new plenticore manager instance."""
        self.hass = hass
        self.config_entry = config_entry

        self._client = None
        self._login = False

        self.device_info = {}

    @property
    def host(self) -> str:
        """Return the host of the Plenticore inverter."""
        return self.config_entry.data[CONF_HOST]

    @property
    def client(self) -> PlenticoreApiClient:
        """Return the Plenticore API client."""
        return self._client

    async def async_setup(self) -> bool:
        """Set up Plenticore API client."""
        self._client = PlenticoreApiClient(
            async_get_clientsession(self.hass), host=self.host
        )
        try:
            await self._client.login(self.config_entry.data[CONF_PASSWORD])
            self._login = True
            _LOGGER.info("Log-in successfully to %s.", self.host)
        except PlenticoreAuthenticationException as err:
            _LOGGER.error(
                "Authentication exception connecting to %s: %s", self.host, err.msg
            )
            raise ConfigEntryNotReady from err
        except (ClientError, asyncio.TimeoutError):
            _LOGGER.exception("Error connecting to %s", self.host)
            return False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting to %s", self.host)
            return False

        # get some device meta data
        settings = await self._client.get_setting_values(
            {
                "devices:local": [
                    "Properties:SerialNo",
                    "Branding:ProductName1",
                    "Branding:ProductName2",
                    "Properties:VersionIOC",
                    "Properties:VersionMC",
                ],
                "scb:network": ["Hostname"],
            }
        )

        device_local = settings["devices:local"]

        self.device_info = {
            "identifiers": {(DOMAIN, device_local["Properties:SerialNo"])},
            "manufacturer": "Kostal",
            "model": device_local["Branding:ProductName1"]
            + " "
            + device_local["Branding:ProductName2"],
            "name": settings["scb:network"]["Hostname"],
            "sw_version": f'IOC: {device_local["Properties:VersionIOC"]}'
            + f' MC: {device_local["Properties:VersionMC"]}',
        }

        return True

    async def logout(self) -> None:
        """Log the current logged in user out from the API."""
        if self._login:
            self._login = False
            await self._client.logout()
            self._client = None
            _LOGGER.info("Logged out from %s.", self.host)


class PlenticoreUpdateCoordinator(DataUpdateCoordinator):
    """Base implementation of DataUpdateCoordinator for Plenticore data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        update_inverval: timedelta,
        plenticore: Plenticore,
    ):
        """Create a new update coordinator for plenticore data."""
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=update_inverval,
            update_method=self._fetch_data,
        )

        self.hass = hass

        # cache for the fetched data
        self._data = {}

        # data ids to poll
        self._fetch = defaultdict(list)

        self._plenticore = plenticore

    def start_fetch_data(self, module_id: str, data_id: str) -> None:
        """Start fetching the given data (module-id and data-id)."""
        self._fetch[module_id].append(data_id)

        # Force an update of all data. Multiple refresh calls
        # are ignored by the debouncer.
        def force_refresh(job: HassJob) -> None:
            self.hass.async_run_job(self.async_request_refresh)

        async_call_later(self.hass, 2, force_refresh)

    def stop_fetch_data(self, module_id: str, data_id: str) -> None:
        """Stop fetching the given data (module-id and data-id)."""
        self._fetch[module_id].remove(data_id)

    async def _fetch_data(self) -> Dict[str, Dict[str, str]]:
        raise NotImplementedError()


class ProcessDataUpdateCoordinator(PlenticoreUpdateCoordinator):
    """Implementation of PlenticoreUpdateCoordinator for process data."""

    async def _fetch_data(self) -> Dict[str, Dict[str, str]]:
        client = self._plenticore.client

        if len(self._fetch) == 0 or client is None:
            return {}

        _LOGGER.debug("Fetching %s for %s", self.name, self._fetch)

        fetched_data = await client.get_process_data_values(self._fetch)
        self._data = {
            m: {pd.id: pd.value for pd in fetched_data[m]} for m in fetched_data
        }

        return self._data


class SettingDataUpdateCoordinator(PlenticoreUpdateCoordinator):
    """Implementation of PlenticoreUpdateCoordinator for settings data."""

    async def _fetch_data(self) -> Dict[str, Dict[str, str]]:
        client = self._plenticore.client

        if len(self._fetch) == 0 or client is None:
            return {}

        _LOGGER.debug("Fetching %s for %s", self.name, self._fetch)

        fetched_data = await client.get_setting_values(self._fetch)

        return fetched_data


class PlenticoreDataFormatter:
    """Provides method to format values of process or settings data."""

    @classmethod
    def get_method(cls, name: str) -> callable:
        """Return a callable formatter of the given name."""
        return getattr(cls, name)

    @staticmethod
    def format_round(state: str) -> Union[int, str]:
        """Return the given state value as rounded integer."""
        try:
            return round(float(state))
        except (TypeError, ValueError):
            return state

    @staticmethod
    def format_energy(state: str) -> Union[float, str]:
        """Return the given state value as energy value, scaled to kWh."""
        try:
            return round(float(state) / 1000, 1)
        except (TypeError, ValueError):
            return state

    @staticmethod
    def format_inverter_state(state: str) -> str:
        """Return a readable string of the inverter state."""
        try:
            value = int(state)
        except (TypeError, ValueError):
            return state

        if value == 0:
            return "Off"
        if value == 1:
            return "Init"
        if value == 2:
            return "IsoMEas"
        if value == 3:
            return "GridCheck"
        if value == 4:
            return "StartUp"
        if value == 6:
            return "FeedIn"
        if value == 7:
            return "Throttled"
        if value == 8:
            return "ExtSwitchOff"
        if value == 9:
            return "Update"
        if value == 10:
            return "Standby"
        if value == 11:
            return "GridSync"
        if value == 12:
            return "GridPreCheck"
        if value == 13:
            return "GridSwitchOff"
        if value == 14:
            return "Overheating"
        if value == 15:
            return "Shutdown"
        if value == 16:
            return "ImproperDcVoltage"
        if value == 17:
            return "ESB"
        return "Unknown"

    @staticmethod
    def format_em_manager_state(state: str) -> str:
        """Return a readable state of the energy manager."""
        try:
            value = int(state)
        except (TypeError, ValueError):
            return state

        if value == 0:
            return "Idle"
        if value == 1:
            return "n/a"
        if value == 2:
            return "Emergency Battery Charge"
        if value == 4:
            return "n/a"
        if value == 8:
            return "Winter Mode Step 1"
        if value == 16:
            return "Winter Mode Step 2"

        return "Unknown"
