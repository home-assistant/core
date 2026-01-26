"""TFA.me station integration: coordinator.py."""

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOCAL_POLL_INTERVAL, VALID_JSON_KEYS
from .data import resolve_tfa_host

_LOGGER = logging.getLogger(__name__)

type TFAmeConfigEntry = ConfigEntry[TFAmeDataCoordinator]


class TFAmeDataCoordinator(DataUpdateCoordinator):
    """Class for managing data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: str,
        name_with_station_id: bool,
    ) -> None:
        """Initialize data update coordinator."""
        self.host = host  # from config_entry.data[CONF_IP_ADDRESS]
        self.first_init = 0
        self.sensor_entity_list: list[str] = []  # [Entity ID strings]
        self.name_with_station_id = (
            name_with_station_id  # from config_entry.data[CONF_NAME_WITH_STATION_ID]
        )
        self.gateway_id = ""
        self.gateway_sw = ""

        # Resolve host only once for client construction:
        resolved_host = resolve_tfa_host(host)

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

    async def _async_update_data(self):
        """Request and update data."""
        parsed_data = {}  # dict for coordinator data

        # Try to update data from station URL: e.g. "http://192.168.1.38/sensors"
        try:
            # Fetch all available sensors as JSON from TFA.me station
            json_data = await self._client.async_get_sensors()

            # Convert JSON to entities dict. for HA coordinator
            parsed_data = self.json_to_entities(json_data=json_data)

        # Specific error mapping
        except (TFAmeHTTPError, TFAmeJSONError) as err:
            # Device responding but data invalid
            _LOGGER.exception("Invalid response from TFA.me gateway %s", self.host)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response_error",
                translation_placeholders={
                    "error": str(err),
                },
            ) from err

        except (TFAmeTimeoutError, TFAmeConnectionError, TFAmeException) as err:
            # Timeout, connection error, other unknown client error
            _LOGGER.exception("Error while updating TFA.me data from %s", self.host)
            if self.first_init == 0:
                raise ConfigEntryNotReady(
                    translation_domain="my_integration",
                    translation_key="cannot_reach_host",
                    translation_placeholders={
                        "host": self.host,
                        "error": str(err),
                    },
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={
                    "error": str(err),
                },
            ) from err

        except Exception as err:  # Fallback for unexpected errors
            _LOGGER.exception(
                "Unexpected error while updating TFA.me data from %s", self.host
            )
            if self.first_init == 0:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="unexpected_error",
                    translation_placeholders={
                        "error": str(err),
                    },
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unexpected_error",
                translation_placeholders={
                    "error": str(err),
                },
            ) from err

        else:
            if self.first_init < 2:
                self.first_init += 1

            # values are available at self.coordinator.data[self.entity_id]["keyword"]
            return parsed_data

    def json_to_entities(self, json_data: dict) -> Any:
        """Convert a TFA.me JSON dictionary into a HA dictionary for coordinator."""
        parsed_data = {}

        try:
            # Get gateway ID
            gateway_id: str = json_data.get("gateway_id", "tfame")
            gateway_id = gateway_id.lower()
            self.gateway_id = gateway_id  # Gateway/station ID
            self.gateway_sw = json_data.get("gateway_sw", "?")

            for sensor in json_data.get("sensors", []):
                sensor_id = sensor["sensor_id"]

                for m_name, values in sensor.get("measurements", {}).items():
                    if measuerment_in_list(m_name, VALID_JSON_KEYS):
                        # Unique ID build of "unique station/gateway ID" & "unique sensor ID"  & measurement name
                        # (IDs set while production process)
                        unique_id = f"sensor.{gateway_id}_{sensor_id}_{m_name}"

                        # Minimum base data for all entities: value, unit, ts (timestamp)
                        base = {
                            "value": values["value"],  # Measurement value
                            "unit": values["unit"],  # Measurement unit
                            "ts": sensor["ts"],  # UTC reception time stamp in seconds
                        }
                        parsed_data[unique_id] = base

                        # Special cases
                        # Wind direction: create extra entity for degrees
                        if m_name == "wind_direction":
                            deg_id = f"{unique_id}_deg"
                            parsed_data[deg_id] = {
                                **base,
                                "unit": "°",
                            }

                        # Rain: create extra entity relative, 1 hour, 24 hours
                        if m_name == "rain":
                            # relative
                            parsed_data[f"{unique_id}_rel"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 1 hour rain
                            parsed_data[f"{unique_id}_1_hour"] = {
                                **base,
                                "reset_rain": False,
                            }

                            # 24 hours rain
                            parsed_data[f"{unique_id}_24_hours"] = {
                                **base,
                                "reset_rain": False,
                            }

        except Exception as err:
            raise TFAmeJSONError(f"Invalid JSON response: {err}") from err
        else:
            return parsed_data


def measuerment_in_list(s: str, m_list: list[str]) -> bool:
    """Search whether a string is in list or not."""
    return s in m_list
