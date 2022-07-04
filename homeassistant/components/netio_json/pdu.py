"""Code to handle a NetIO PDU with JSON/http."""
from __future__ import annotations

from datetime import datetime
import logging

from Netio import Netio
from Netio.exceptions import AuthError, CommunicationError
import aiohttp
import async_timeout
from requests.exceptions import ConnectionError as requestsConnectionError

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (  # API_AGENT_UPTIME,
    API_AGENT,
    API_AGENT_DEVICENAME,
    API_AGENT_MAC,
    API_AGENT_MODEL,
    API_AGENT_NUMINPUTS,
    API_AGENT_NUMOUTPUTS,
    API_AGENT_SERIALNUMBER,
    API_AGENT_VERSION,
    API_GLOBAL_ENERGY_START,
    API_GLOBAL_MEASURE,
    API_OUTLET,
    DOMAIN,
    SCAN_INTERVAL,
)

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
            resp = await session.get(config_url, auth=auth)
        except aiohttp.ClientConnectionError as ex:
            _LOGGER.warning("Failed to connect: %s", ex)
            raise CannotConnect from ex
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            _LOGGER.warning(message)
            raise CannotConnect from ex

    if 401 <= resp.status <= 403:
        _LOGGER.warning("Failed to authenticate")
        raise InvalidAuth(resp.status)
    return True


class NetioPDU:
    """Manage a single NetIO PDU."""

    def __init__(self, hass: core.HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self._host: str = self.config_entry.data["host"]
        self._config_url: str = _get_config_url(
            self.host, self.config_entry.data["ssl"]
        )
        self._read_only: bool = self.config_entry.data["ro"]
        self._model: str | None = None
        self._device_name: str | None = None
        self._mac: str | None = None
        self._serial_number: str | None = None
        self._num_output: int | None = None
        self._num_input: int | None = None
        self._sw_version: str | None = None
        self._energy_start: datetime | None = None
        if self._read_only:
            self.pdu = Netio(
                self._config_url,
                auth_r=(
                    f"{self.config_entry.data['username']}",
                    f"{self.config_entry.data['password']}",
                ),
                verify=False,
                skip_init=True,
            )
        else:
            self.pdu = Netio(
                self._config_url,
                auth_rw=(
                    f"{self.config_entry.data['username']}",
                    f"{self.config_entry.data['password']}",
                ),
                verify=False,
                skip_init=True,
            )
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

    @property
    def serial_number(self) -> str:
        """Return the devices serial number."""
        return str(self._serial_number)

    @property
    def host(self) -> str:
        """Return the device hostname."""
        return self._host

    @property
    def read_only(self) -> bool:
        """Return the read_only state of this connection."""
        return self._read_only

    @property
    def sw_version(self) -> str:
        """Return the software version of the PDU."""
        return str(self._sw_version)

    @property
    def energy_start(self) -> datetime | None:
        """Return the last reset moment of the PDU."""
        return self._energy_start

    @property
    def model(self) -> str:
        """Return the PDU model string."""
        return str(self._model)

    @property
    def device_name(self) -> str:
        """Return the PDU device name."""
        return str(self._device_name)

    async def async_initialize_pdu(self) -> None:
        """Initialize connection with the NetIO PDU."""
        try:
            await self.hass.async_add_executor_job(self.pdu.init)
        except (CommunicationError, AuthError, ValueError) as ex:
            raise ConnectionError(ex) from ex
        except requestsConnectionError as ex:
            raise ConnectionError(ex) from ex

        info = await self.hass.async_add_executor_job(self.pdu.get_info)
        self._model = self._get_device_model(info[API_AGENT][API_AGENT_MODEL])
        self._device_name = info[API_AGENT][API_AGENT_DEVICENAME]
        self._mac = info[API_AGENT][API_AGENT_MAC]
        self._serial_number = info[API_AGENT][API_AGENT_SERIALNUMBER]
        self._num_output = info[API_AGENT][API_AGENT_NUMOUTPUTS]
        self._num_input = info[API_AGENT][API_AGENT_NUMINPUTS]
        self._sw_version = info[API_AGENT][API_AGENT_VERSION]
        self._energy_start = datetime.strptime(
            info[API_GLOBAL_MEASURE][API_GLOBAL_ENERGY_START], "%Y-%m-%dT%H:%M:%S%z"
        )

    def ready(self) -> bool:
        """Return True if device MAC is set."""
        if self._mac is not None:
            return True
        return False

    async def async_get_state(self) -> None:
        """Get the state of the NetIO PDU."""
        try:
            data = await self.hass.async_add_executor_job(self.pdu.get_info)
            data[API_OUTLET] = {}
            outputs = await self.hass.async_add_executor_job(self.pdu.get_outputs)
            for out in outputs:
                outdict = out._asdict()
                data[API_OUTLET][outdict["ID"]] = outdict
        except KeyError:
            return None
        return data

    def output_count(self) -> int | None:
        """Return the number of outputs."""
        return self._num_output

    def output_off(self, output: int) -> None:
        """Turn an output off."""
        if self._read_only:
            raise NotImplementedError("Device is configured as Read Only")
        self.pdu.set_output(output, Netio.ACTION.OFF)

    def output_on(self, output: int) -> None:
        """Turn an output on."""
        if self._read_only:
            raise NotImplementedError("Device is configured as Read Only")
        self.pdu.set_output(output, Netio.ACTION.ON)

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
