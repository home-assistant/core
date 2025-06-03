"""Config flow for israel rail."""

import logging
from typing import Any

from israelrailapi import TrainSchedule
from israelrailapi.stations import STATIONS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DESTINATION, CONF_START, DOMAIN

STATIONS_NAMES = [station["Heb"] for station in STATIONS.values()]
STATIONS_NAMES.sort()

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): vol.In(STATIONS_NAMES),
        vol.Required(CONF_DESTINATION): vol.In(STATIONS_NAMES),
    }
)

_LOGGER = logging.getLogger(__name__)


class IsraelRailConfigFlow(ConfigFlow, domain=DOMAIN):
    """Israel rail config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async user step to set up the connection."""
        errors = {}
        if user_input:
            train_schedule = TrainSchedule()
            try:
                await self.hass.async_add_executor_job(
                    train_schedule.query,
                    user_input[CONF_START],
                    user_input[CONF_DESTINATION],
                )
            except Exception:
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            if not errors:
                unique_id = f"{user_input[CONF_START]} {user_input[CONF_DESTINATION]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=unique_id,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
