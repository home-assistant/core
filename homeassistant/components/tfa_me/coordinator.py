"""TFA.me station integration: coordinator.py."""

from dataclasses import dataclass
import logging
from typing import Any

from tfa_me_ha_local.client import (
    TFAmeClient,
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.components.sensor import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_NAME_WITH_STATION_ID,
    DOMAIN,
    LOCAL_POLL_INTERVAL,
    VALID_JSON_KEYS,
)
from .data import resolve_tfa_host

_LOGGER = logging.getLogger(__name__)


@dataclass
class TFAmeCoordinatorData:
    """Typed coordinator payload."""

    entities: dict[
        str, dict[str, Any]
    ]  # dict with unique IDs & measurement data, units, timestamp and more
    gateway_id: str  # 9 digit gateway/station serial hex number
    gateway_sw: str  # SW numbers (gateway/station & display unit)


type TFAmeConfigEntry = ConfigEntry[TFAmeDataCoordinator]


class TFAmeDataCoordinator(DataUpdateCoordinator[TFAmeCoordinatorData]):
    """Class for managing data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize data update coordinator."""

        self.host = config_entry.data[CONF_IP_ADDRESS]  # Get IP or station-ID
        self.name_with_station_id = config_entry.data[
            CONF_NAME_WITH_STATION_ID
        ]  # Use name with station ID option
        self.sensor_entity_list: list[str] = []  # [Entity ID strings]

        # Resolve host only once for client construction:
        resolved_host = resolve_tfa_host(self.host)

        # Create a single reusable TFA.me client
        session = async_get_clientsession(hass)
        self._client = TFAmeClient(
            resolved_host, "sensors", log_level=1, session=session, timeout=10
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=LOCAL_POLL_INTERVAL),
        )

    async def _async_update_data(self) -> TFAmeCoordinatorData:
        """Request and update data."""
        parsed_list: dict[str, dict[str, Any]] = {}  # dict for coordinator data

        # Try to update data from station URL: e.g. "http://192.168.1.38/sensors"
        try:
            # Fetch all available sensors as JSON from TFA.me station
            json_data = await self._client.async_get_sensors()

            # Convert JSON to values for TFAmeCoordinatorData for coordinator
            parsed_list, gateway_id, gateway_sw = self.parse_json(json_data)

        # Specific error mapping
        except (TFAmeHTTPError, TFAmeJSONError) as err:
            # Device responding but data invalid
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_error",
            ) from err

        except (TFAmeTimeoutError, TFAmeConnectionError, TFAmeException) as err:
            # Timeout, connection error, other unknown client error
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err

        else:
            # values are available at self.coordinator.data.entities[self.entity_id]["keyword"]
            return TFAmeCoordinatorData(
                entities=parsed_list, gateway_id=gateway_id, gateway_sw=gateway_sw
            )

    def parse_json(
        self, json_data: dict[str, Any]
    ) -> tuple[dict[str, dict[str, Any]], str, str]:
        """Parse a TFA.me JSON dictionary to get TFAmeCoordinatorData values for coordinator."""
        parsed_list: dict[
            str, dict[str, Any]
        ] = {}  # dict with unique IDs & measurement data, units, etc.

        try:
            # Get gateway ID, SW version & sensor list
            gateway_id = str(json_data.get("gateway_id", "tfame")).lower()
            gateway_sw = str(json_data.get("gateway_sw", "?"))
            sensors = json_data.get("sensors", [])

            for sensor in sensors:
                sensor_id = sensor["sensor_id"]

                for m_name, values in sensor.get("measurements", {}).items():
                    if measurement_in_list(m_name, VALID_JSON_KEYS):
                        # Unique ID build of "unique station/gateway ID" & "unique sensor ID"  & measurement name
                        # (IDs set while production process)
                        unique_id = f"sensor.{gateway_id}_{sensor_id}_{m_name}"

                        # Minimum base data for all entities: value, unit, ts (timestamp)
                        base = {
                            "value": values["value"],  # Measurement value
                            "unit": values["unit"],  # Measurement unit
                            "ts": sensor["ts"],  # UTC reception time stamp in seconds
                        }
                        parsed_list[unique_id] = base

                        # Special cases
                        # Wind direction: create extra entity for degrees
                        if m_name == "wind_direction":
                            deg_id = f"{unique_id}_deg"
                            parsed_list[deg_id] = {
                                **base,
                                "unit": "°",
                            }

                        # Rain: create extra entity relative, 1 hour, 24 hours
                        if m_name == "rain":
                            # relative
                            parsed_list[f"{unique_id}_rel"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 1 hour rain
                            parsed_list[f"{unique_id}_1_hour"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 24 hours rain
                            parsed_list[f"{unique_id}_24_hours"] = {
                                **base,
                                "reset_rain": False,
                            }

        except Exception as err:
            raise TFAmeJSONError(f"Invalid JSON response: {err}") from err
        else:
            return parsed_list, gateway_id, gateway_sw


def measurement_in_list(s: str, m_list: list[str]) -> bool:
    """Search whether a string is in list or not."""
    return s in m_list
