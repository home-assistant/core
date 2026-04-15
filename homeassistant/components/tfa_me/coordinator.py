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
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_NAME_WITH_STATION_ID,
    DOMAIN,
    LOCAL_POLL_INTERVAL,
    VALID_JSON_MEASUREMENT_KEYS,
)
from .data import TFAmeCoordinatorData, resolve_tfa_host

_LOGGER = logging.getLogger(__name__)


type TFAmeConfigEntry = ConfigEntry[TFAmeUpdateCoordinator]


class TFAmeUpdateCoordinator(DataUpdateCoordinator[TFAmeCoordinatorData]):
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
        filtered_list: dict[str, dict[str, Any]] = {}  # filtered entity list

        # Try to update data from station URL: e.g. "http://192.168.1.38/sensors"
        try:
            # Fetch all available sensors as JSON from TFA.me station/gateway
            json_data = await self._client.async_get_sensors()

            # Convert JSON to values for TFAmeCoordinatorData for coordinator
            # Also filter/remove values/entities that integration is unable to process
            filtered_list, gateway_id, gateway_sw = self._client.parse_and_filter_json(
                json_data=json_data, valid_keys=VALID_JSON_MEASUREMENT_KEYS
            )

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
                entities=filtered_list, gateway_id=gateway_id, gateway_sw=gateway_sw
            )
