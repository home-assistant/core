"""Config flow for Swiss Hydrological Data."""

import logging
from typing import Any

from requests.exceptions import RequestException
from swisshydrodata import SwissHydroData
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATION): vol.Coerce(int),
    }
)


class SwissHydrologicalDataConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swiss Hydrological Data."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id: int = user_input[CONF_STATION]

            await self.async_set_unique_id(str(station_id))
            self._abort_if_unique_id_configured()

            try:
                data = await self.hass.async_add_executor_job(
                    self._fetch_station, station_id
                )
            except RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error during Swiss Hydrological Data setup"
                )
                errors["base"] = "unknown"
            else:
                if data is None:
                    errors["base"] = "invalid_station"
                else:
                    return self.async_create_entry(
                        title=f"{data['water-body-name']} {data['name']}",
                        data={CONF_STATION: station_id},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _fetch_station(self, station_id: int) -> dict[str, Any] | None:
        """Fetch station data synchronously."""
        return SwissHydroData().get_station(station_id)
