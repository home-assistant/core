"""Schluter DITRA-HEAT API client."""

from dataclasses import dataclass
import logging

from aiohttp import ClientError, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://ditra-heat-e-wifi.schluter.com"
API_APPLICATION_ID = 7


class InvalidCredentialsError(Exception):
    """Raised when the provided credentials are rejected by the API."""


class InvalidSessionError(Exception):
    """Raised when the session token is expired or invalid."""


class CannotConnectError(Exception):
    """Raised when a network or HTTP error prevents communication with the API."""


@dataclass
class SchluterThermostat:
    """Represents a single Schluter DITRA-HEAT thermostat."""

    serial_number: str
    name: str
    temperature: float
    set_point_temp: float
    min_temp: float
    max_temp: float
    is_heating: bool
    is_online: bool
    load_measured_watt: int
    sw_version: str


def _to_celsius(value: int) -> float:
    """Convert an API integer temperature value to Celsius, rounded to 0.5°C."""
    return round(round(value / 100, 1) / 0.5) * 0.5


def _parse_thermostat(data: dict) -> SchluterThermostat:
    """Parse a raw API thermostat dict into a SchluterThermostat dataclass."""
    return SchluterThermostat(
        serial_number=data["SerialNumber"],
        name=data["Room"],
        temperature=_to_celsius(data["Temperature"]),
        set_point_temp=_to_celsius(data["SetPointTemp"]),
        min_temp=_to_celsius(data["MinTemp"]),
        max_temp=_to_celsius(data["MaxTemp"]),
        is_heating=bool(data.get("Heating")),
        is_online=bool(data.get("Online")),
        load_measured_watt=int(data.get("LoadMeasuredWatt", 0)),
        sw_version=str(data.get("SWVersion", "")),
    )


class SchluterApi:
    """Async HTTP client for the Schluter DITRA-HEAT cloud API."""

    def __init__(self, websession: ClientSession) -> None:
        """Initialize with an aiohttp ClientSession."""
        self._websession = websession

    async def async_get_session(self, email: str, password: str) -> str:
        """Authenticate and return a session token.

        Raises InvalidCredentialsError if the credentials are rejected.
        Raises CannotConnectError on network or unexpected HTTP errors.
        """
        try:
            async with self._websession.post(
                f"{API_BASE_URL}/api/authenticate/user",
                json={
                    "Email": email,
                    "Password": password,
                    "Application": API_APPLICATION_ID,
                },
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except ClientResponseError as err:
            raise CannotConnectError(str(err)) from err
        except ClientError as err:
            raise CannotConnectError(str(err)) from err

        if data.get("ErrorCode") in (1, 2):
            raise InvalidCredentialsError

        return data["SessionId"]

    async def async_get_thermostats(self, session_id: str) -> list[SchluterThermostat]:
        """Return all thermostats for the given session.

        Raises InvalidSessionError if the session is expired or invalid.
        Raises CannotConnectError on network or unexpected HTTP errors.
        """
        try:
            async with self._websession.get(
                f"{API_BASE_URL}/api/thermostats",
                params={"sessionId": session_id},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except ClientResponseError as err:
            if err.status == 401:
                raise InvalidSessionError from err
            raise CannotConnectError(str(err)) from err
        except ClientError as err:
            raise CannotConnectError(str(err)) from err

        groups = data.get("Groups")
        if not groups:
            raise InvalidSessionError

        return [
            _parse_thermostat(thermo)
            for group in groups
            for thermo in group.get("Thermostats", [])
        ]

    async def async_set_temperature(
        self, session_id: str, serial_number: str, temperature: float
    ) -> None:
        """Set the target temperature for a thermostat.

        Raises InvalidSessionError if the session is expired or invalid.
        Raises CannotConnectError on network or unexpected HTTP errors.
        """
        try:
            async with self._websession.post(
                f"{API_BASE_URL}/api/thermostat",
                params={"sessionId": session_id, "serialnumber": serial_number},
                json={
                    "ManualTemperature": int(temperature * 100),
                    "RegulationMode": 3,
                    "VacationEnabled": False,
                },
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
        except ClientResponseError as err:
            if err.status == 401:
                raise InvalidSessionError from err
            raise CannotConnectError(str(err)) from err
        except ClientError as err:
            raise CannotConnectError(str(err)) from err

        if not result.get("Success"):
            raise CannotConnectError("API returned Success=false for set_temperature")
