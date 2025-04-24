"""Models and API client for the Autoskope integration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import APP_VERSION, DEFAULT_MODEL, DEVICE_TYPE_MODELS

if TYPE_CHECKING:
    from .coordinator import AutoskopeDataUpdateCoordinator


_LOGGER: Final = logging.getLogger(__name__)


class GeoJsonProperties(TypedDict, total=False):
    """TypedDict for GeoJSON properties relevant to Autoskope."""

    s: str | float  # Speed
    dt: str  # Timestamp
    park: bool | int  # Park mode (can be 0/1 or boolean) # Changed comment
    carid: str | int  # Vehicle ID


class GeoJsonGeometry(TypedDict):
    """TypedDict for GeoJSON geometry."""

    type: str
    coordinates: list[float]


class GeoJsonFeature(TypedDict):
    """TypedDict for a GeoJSON feature."""

    type: str
    geometry: GeoJsonGeometry
    properties: GeoJsonProperties


@dataclass
class VehiclePosition:
    """Position information extracted from GeoJSON."""

    latitude: float
    longitude: float
    speed: float
    timestamp: str
    park_mode: bool

    @classmethod
    def from_geojson(cls, feature: GeoJsonFeature) -> VehiclePosition | None:
        """Create VehiclePosition from a GeoJSON feature dictionary."""
        try:
            geometry = feature["geometry"]
            props = feature["properties"]
            coords = geometry["coordinates"]
            if len(coords) < 2:
                _LOGGER.debug("Invalid coordinates in GeoJSON feature: %s", coords)
                return None
        except (KeyError, TypeError, IndexError) as err:
            _LOGGER.debug("Error accessing required GeoJSON structure: %s", err)
            return None

        # Parse properties with error handling and defaults
        try:
            speed = float(props.get("s", 0.0))
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid speed value in GeoJSON: %s", props.get("s"))
            speed = 0.0
        try:
            # Handle '0'/'1' or boolean for park mode
            park_val = props.get("park", 0)
            park_mode = (
                bool(int(park_val))
                if isinstance(park_val, (str, int))
                else bool(park_val)
            )
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid park value in GeoJSON: %s", props.get("park"))
            park_mode = False
        try:
            # Timestamp is expected
            timestamp = str(props["dt"])
        except KeyError:
            _LOGGER.debug("Missing timestamp (dt) in GeoJSON properties")
            return None  # Position is not valid without a timestamp

        return cls(
            latitude=coords[1],
            longitude=coords[0],
            speed=speed,
            timestamp=timestamp,
            park_mode=park_mode,
        )


def _find_and_parse_position(
    vehicle_id: str, position_data: PositionDataApi | None
) -> VehiclePosition | None:
    """Find and parse the position for a specific vehicle ID from position data."""
    if not position_data or not (features := position_data.get("features")):
        return None
    if not isinstance(features, list):
        _LOGGER.debug("Features data is not a list: %s", features)  # type: ignore[unreachable]
        return None

    for feature in features:
        # Ensure feature is a dict and has properties before checking carid
        if not isinstance(feature, dict) or not (props := feature.get("properties")):
            _LOGGER.debug("Skipping feature with unexpected structure: %s", feature)
            continue  # Skip this feature

        if isinstance(props, dict) and str(props.get("carid")) == vehicle_id:
            # Pass the feature directly if it matches GeoJsonFeature structure
            position = VehiclePosition.from_geojson(feature)
            if position:
                return position  # Found and parsed position for this vehicle

    return None


class VehicleInfoApi(TypedDict):
    """TypedDict for the 'info' part of the vehicle data from API."""

    id: str | int
    name: str
    ex_pow: str | float | int
    bat_pow: str | float | int
    hdop: str | float | int
    support_infos: dict[str, Any] | None
    device_type_id: str | int | None


class PositionDataApi(TypedDict, total=False):
    """TypedDict for the 'position_data' structure from API."""

    features: list[GeoJsonFeature]


@dataclass
class Vehicle:
    """Class representing a vehicle."""

    id: str
    name: str
    position: VehiclePosition | None
    external_voltage: float
    battery_voltage: float
    gps_quality: float  # Lower is better (HDOP)
    imei: str | None
    model: str

    @classmethod
    def from_api(
        cls,
        info: VehicleInfoApi,
        position_data: PositionDataApi | None = None,
    ) -> Vehicle:
        """Create Vehicle object from API response dictionaries."""
        try:
            vehicle_id = str(info["id"])
            name = info["name"]
            # Convert numeric fields robustly
            ex_pow = float(info["ex_pow"])
            bat_pow = float(info["bat_pow"])
            hdop = float(info["hdop"])
        except (KeyError, ValueError, TypeError) as err:
            _LOGGER.warning("Missing or invalid required vehicle info field: %s", err)
            # Raise ValueError to be caught by the caller (get_vehicles)
            raise ValueError(f"Invalid vehicle data structure: {err}") from err

        # Use helper function to find position
        position = _find_and_parse_position(vehicle_id, position_data)

        # Use .get() for optional fields/dicts
        support_infos = info.get("support_infos")
        imei = support_infos.get("imei") if isinstance(support_infos, dict) else None
        device_type = str(info.get("device_type_id", ""))
        model = DEVICE_TYPE_MODELS.get(device_type, DEFAULT_MODEL)

        return cls(
            id=vehicle_id,
            name=name,
            position=position,
            external_voltage=ex_pow,
            battery_voltage=bat_pow,
            gps_quality=hdop,
            imei=imei,
            model=model,
        )


class AutoskopeApi:
    """Client to interact with the Autoskope API."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the Autoskope API client."""
        self._host = host.rstrip("/")
        self._username = username
        self._password = password
        self._hass = hass
        self._form_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        self._json_headers = {"Content-Type": "application/json"}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get the ClientSession from Home Assistant."""
        return async_get_clientsession(self._hass)

    async def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request and handle responses."""
        url = f"{self._host}{path}"
        session = await self._get_session()
        headers = self._form_headers  # Default to form headers

        _LOGGER.debug("Requesting %s %s", method.upper(), url)

        response_text: str | None = None
        response_json: dict[str, Any] | None = None
        error_to_raise: Exception | None = None

        try:
            async with session.request(
                method,
                url,
                headers=headers,
                data=data,
                **kwargs,
            ) as response:
                response_status = response.status
                response.headers.get("Content-Type", "").lower()
                _LOGGER.debug("Response status for %s: %s", url, response_status)

                response_text = await response.text()

                # Handle status 202 specifically: Success, but check for outdated message
                if response_status == 202:
                    _LOGGER.debug(
                        "Login response body (status 202): %s", response_text[:200]
                    )
                    try:
                        response_json_202 = json.loads(response_text)
                        if isinstance(response_json_202, dict) and (
                            message := response_json_202.get("message")
                        ):
                            if isinstance(message, str) and message.startswith(
                                "Du verwendest eine veraltete App-Version"
                            ):
                                # Log as warning but continue as success
                                _LOGGER.debug(
                                    "API reports outdated client version, but proceeding: %s",
                                    message,
                                )
                    except json.JSONDecodeError:
                        _LOGGER.debug(
                            "Received non-JSON response on status 202, proceeding anyway"
                        )
                    # Treat status 202 as successful authentication by returning empty dict
                    return {}

                # Handle login response specifically (Status 200)
                if path == "/scripts/ajax/login.php":
                    _LOGGER.debug(
                        "Login response body (status %s): %s",
                        response_status,
                        response_text[:200],
                    )
                    if response_status == 200 and not response_text.strip():
                        return {}  # Success, return empty dict
                    # Store error for login failure (non-200 or non-empty body)
                    error_to_raise = InvalidAuth(
                        "Authentication failed (non-200 status or non-empty body)"
                    )
                # Check for auth errors (e.g., wrong password, session expired)
                elif response_status in (401, 403):
                    error_to_raise = InvalidAuth(
                        f"Authorization error: {response_status}"
                    )
                # Check for other client/server errors
                elif response_status >= 400:
                    # Store error for other bad statuses
                    error_to_raise = CannotConnect(
                        f"API request failed with status {response_status}"
                    )
                # Process successful response (usually 200 for non-login requests)
                else:
                    # Try parsing as JSON, even if content-type isn't strictly JSON
                    try:
                        response_json = json.loads(response_text)
                        if not isinstance(response_json, dict):
                            _LOGGER.warning("API response is not a JSON dictionary")
                            # Store error for unexpected format
                            error_to_raise = CannotConnect(
                                "Received non-dictionary JSON response from API"
                            )
                    except json.JSONDecodeError as json_err:
                        # Check if it's the login page HTML indicating session expiry
                        if (
                            "<title>Login</title>" in response_text
                            or "login.php" in response_text
                        ):
                            _LOGGER.warning(
                                "Received login page response, session likely expired"
                            )
                            error_to_raise = InvalidAuth(
                                "Session likely expired, received login page"
                            )
                        else:
                            _LOGGER.error("Failed to decode API response: %s", json_err)
                            # Store error for invalid format
                            error_to_raise = CannotConnect(
                                "Received invalid response from API"
                            )
                            error_to_raise.__cause__ = json_err

        except aiohttp.ClientError as err:
            _LOGGER.error("API request connection error for %s: %s", url, err)
            # Raise CannotConnect for network/connection issues
            raise CannotConnect(f"Error connecting to Autoskope API: {err}") from err
        except Exception as err:
            # Catch any other unexpected errors during the request process
            _LOGGER.exception("Unexpected error during API request to %s", url)
            # Raise CannotConnect for unexpected issues during request
            raise CannotConnect(f"Unexpected API error: {err}") from err

        # Raise any stored errors after the try block
        if error_to_raise:
            raise error_to_raise

        # Return the processed JSON response if no errors occurred
        # Ensure a dict is returned even if parsing failed but no error was stored
        return response_json if response_json is not None else {}

    async def authenticate(self) -> bool:
        """Authenticate with the API and verify success."""
        try:
            # Request returns empty dict on success, raises on failure
            await self._request(
                "post",
                "/scripts/ajax/login.php",
                data={
                    "username": self._username,
                    "password": self._password,
                    "appversion": APP_VERSION,
                },
                timeout=10,
            )
        except InvalidAuth as err:
            _LOGGER.warning("Authentication failed for user %s", self._username)
            raise InvalidAuth("Authentication failed") from err
        except CannotConnect as err:
            _LOGGER.error(
                "Connection error during authentication for user %s", self._username
            )
            raise CannotConnect("Connection error during authentication") from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error during authentication for user %s", self._username
            )
            raise CannotConnect(
                f"Unexpected error during authentication: {err}"
            ) from err
        else:
            _LOGGER.debug("Authentication successful for user %s", self._username)
            return True

    async def get_vehicles(self) -> list[Vehicle]:
        """Fetch and parse vehicles data from the API."""
        _LOGGER.debug("Attempting to fetch vehicle data")
        vehicles: list[Vehicle] = []
        error_to_raise: Exception | None = None

        try:
            data = await self._request(
                "post",
                "/scripts/ajax/app/info.php",
                data={"appversion": APP_VERSION},
                timeout=20,
            )

            position_data = None
            last_pos_str = data.get("lastPos")
            if isinstance(last_pos_str, str) and last_pos_str:
                try:
                    position_data = json.loads(last_pos_str)
                    if not isinstance(position_data, dict):
                        _LOGGER.warning("Parsed lastPos data is not a dictionary")
                        position_data = None  # Treat as invalid
                except json.JSONDecodeError:
                    _LOGGER.warning("Failed to parse lastPos JSON string")
            elif last_pos_str is not None:  # Log if it exists but isn't a string
                _LOGGER.warning(
                    "The lastPos data is not a string: %s", type(last_pos_str)
                )

            cars_list = data.get("cars", [])
            if not isinstance(cars_list, list):
                _LOGGER.error("Vehicle data 'cars' is not a list")
                # Store error for invalid format
                error_to_raise = UpdateFailed(
                    "Invalid vehicle data format in API response"
                )
            else:
                # Process cars only if format is correct
                for car_info in cars_list:
                    if not isinstance(car_info, dict):
                        _LOGGER.warning("Skipping non-dictionary item in cars list")
                        continue
                    try:
                        # Attempt to create Vehicle object
                        vehicles.append(
                            Vehicle.from_api(
                                car_info,  # type: ignore[arg-type]
                                position_data,
                            )
                        )
                    except ValueError as e:
                        # Log errors during individual vehicle parsing but continue
                        vehicle_id = car_info.get("id", "unknown")
                        _LOGGER.warning(
                            "Failed to parse vehicle data for ID %s: %s",
                            vehicle_id,
                            e,
                        )

        except InvalidAuth as err:
            _LOGGER.error("Authentication error during vehicle fetch")
            # Let coordinator handle raising ConfigEntryAuthFailed
            raise UpdateFailed("Authentication required") from err
        except CannotConnect as err:
            _LOGGER.error(
                "Failed to fetch vehicle data due to connection/API error: %s", err
            )
            # Raise UpdateFailed for coordinator
            raise UpdateFailed(
                f"Failed to fetch data from Autoskope API: {err}"
            ) from err
        except Exception as err:
            # Catch any other unexpected errors during processing
            _LOGGER.exception("Unexpected error processing vehicle data")
            raise UpdateFailed(
                f"Unexpected error processing vehicle data: {err}"
            ) from err

        # Raise stored errors after try block (e.g., format errors)
        if error_to_raise:
            raise error_to_raise

        # Return vehicles list if no fatal errors occurred
        _LOGGER.debug("Successfully parsed %d vehicles", len(vehicles))
        return vehicles


class AutoskopeError(HomeAssistantError):
    """Base exception for Autoskope errors."""


class CannotConnect(AutoskopeError):
    """Exception raised when connection to the API fails."""


class InvalidAuth(AutoskopeError):
    """Exception raised for authentication errors."""


@dataclass
class AutoskopeRuntimeData:
    """Runtime data for the Autoskope integration."""

    coordinator: AutoskopeDataUpdateCoordinator


# Define the specific ConfigEntry type
type AutoskopeConfigEntry = ConfigEntry[AutoskopeRuntimeData]
