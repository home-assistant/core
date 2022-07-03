"""Code to handle a NetIO PDU with JSON/http."""
from __future__ import annotations

from datetime import datetime
import logging

from Netio import Netio
from Netio.exceptions import AuthError, CommunicationError

# import asyncio
import aiohttp
import async_timeout
from requests.exceptions import ConnectionError as requestsConnectionError

from homeassistant import core
from homeassistant.config_entries import ConfigEntry  # SOURCE_IMPORT,
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_GLOBAL_ENERGY_START,
    API_GLOBAL_MEASURE,
    API_OUTLET,
    DOMAIN,
    SCAN_INTERVAL,
)

# import async_timeout


_LOGGER = logging.getLogger(__name__)


def _get_config_url(host: str, ssl: bool) -> str:
    """Get the correct config url."""
    if ssl:
        return f"https://{host}/netio.json"
    return f"http://{host}/netio.json"


async def validate_pdu_connection(
    host: str,
    username: str = "",
    password: str = "",
    ssl: bool = False,
    is_ro: bool = False,
) -> bool:
    """Check if the connection details are valid."""

    config_url = _get_config_url(host, ssl)

    auth = aiohttp.BasicAuth(username, password)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(config_url, auth=auth) as resp:
                _LOGGER.warning(resp.status)
        except aiohttp.ClientConnectionError as ex:
            _LOGGER.warning("Failed to connect: %s", ex)
            raise CannotConnect from ex
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            _LOGGER.warning(message)
            raise CannotConnect from ex

    if 401 <= resp.status <= 403:
        raise InvalidAuth(resp.status)
    return True


class NetioPDU:
    """Manage a single NetIO PDU."""

    def __init__(self, hass: core.HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.host: str = self.config_entry.data["host"]
        self.config_url: str = _get_config_url(self.host, self.config_entry.data["ssl"])
        self.read_only: bool = self.config_entry.data["ro"]
        self.model: str | None = None
        self.device_name: str | None = None
        self._mac: str | None = None
        self.serial_number: str | None = None
        self._num_output: int | None = None
        self._num_input: int | None = None
        self.sw_version: str | None = None
        self.energy_start: datetime | None = None
        if self.read_only:
            self.pdu = Netio(
                self.config_url,
                auth_r=(
                    f"{self.config_entry.data['username']}",
                    f"{self.config_entry.data['password']}",
                ),
                verify=False,
                skip_init=True,
            )
        else:
            self.pdu = Netio(
                self.config_url,
                auth_rw=(
                    f"{self.config_entry.data['username']}",
                    f"{self.config_entry.data['password']}",
                ),
                verify=False,
                skip_init=True,
            )
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

    async def async_initialize_pdu(self) -> None:
        """Initialize connection with the NetIO PDU."""
        try:
            await self.hass.async_add_executor_job(self.pdu.init)
        except (CommunicationError, AuthError, ValueError) as ex:
            raise ConnectionError(ex) from ex
        except requestsConnectionError as ex:
            raise ConnectionError(ex) from ex

        info = await self.hass.async_add_executor_job(self.pdu.get_info)
        self.model = self._get_device_model(info["Agent"]["Model"])
        self.device_name = info["Agent"]["DeviceName"]
        self._mac = info["Agent"]["MAC"]
        self.serial_number = info["Agent"]["SerialNumber"]
        self._num_output = info["Agent"]["NumOutputs"]
        self._num_input = info["Agent"]["NumInputs"]
        self.sw_version = info["Agent"]["Version"]
        self.energy_start = datetime.strptime(
            info[API_GLOBAL_MEASURE][API_GLOBAL_ENERGY_START], "%Y-%m-%dT%H:%M:%S%z"
        )

    def ready(self) -> bool:
        """Return True if device MAC is set."""
        if self._mac is not None:
            return True
        return False

    async def async_get_state(self) -> None:
        """Get the state of the NetIO PDU."""
        _LOGGER.info("Update PDU")
        try:
            data = await self.hass.async_add_executor_job(self.pdu.get_info)
            data[API_OUTLET] = {}
            outputs = await self.hass.async_add_executor_job(self.pdu.get_outputs)
            for out in outputs:
                outdict = out._asdict()
                # _LOGGER.info(outdict)
                data[API_OUTLET][outdict["ID"]] = outdict
        except KeyError:
            return None
        return data

    def output_count(self) -> int | None:
        """Return the number of outputs."""
        return self._num_output

    def output_off(self, output: int) -> None:
        """Turn an output off."""
        if self.read_only:
            raise NotImplementedError("Device is configured as Read Only")
        self.pdu.set_output(output, Netio.ACTION.OFF)

    def output_on(self, output: int) -> None:
        """Turn an output on."""
        if self.read_only:
            raise NotImplementedError("Device is configured as Read Only")
        self.pdu.set_output(output, Netio.ACTION.ON)

    async def get_outlet(self, outlet: int, key: str) -> str | int | float | None:
        """Return Outlet values."""
        try:
            info = await self.hass.async_add_executor_job(self.pdu.get_output, outlet)
            _LOGGER.warning("OUTLET: %s", info)
            # return info._fields[key]
            return getattr(info, key)
        except KeyError:
            return None

    def _get_device_model(self, model: str) -> str:
        """Return the full device model name."""
        if model.startswith("4P"):
            if model.endswith("S"):
                return "PowerPDU 4PS"
            if model.endswith("Z"):
                return "PowerDIN 4PZ"
            return f"PowerBOX {model}"
        if model.startswith("4K"):
            if model.endswith("S"):
                return "PowerPDU 4KS"
            return f"PowerBOX {model}"
        if model.startswith("3P"):
            return f"PowerBOX {model}"
        if model == "4C":
            return "PowerPDU 4C"
        if model == "8QS":
            return "PowerPDU 8QS"
        return f"UNKNOWN {model}"


class NetioPDUCoordinator(DataUpdateCoordinator):
    """Data Update Coordinator for a NetIO PDU."""

    def __init__(self, hass, pdu):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="NetIO PDU",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        self.pdu = pdu

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # _LOGGER.info("Fetching PDU Data")
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await self.pdu.async_get_state()
        except InvalidAuth as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class CannotConnect(ConnectionError):
    """Error to indicate we cannot connect."""


class InvalidAuth(ConnectionRefusedError):
    """Error to indicate there is invalid auth."""
