"""Config flow to configure Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
    TITLE,
)
from .coordinator import EvoBroker

SCHEMA_USER: Final = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
SCHEMA_LOC_IDX: Final = vol.Schema(
    {
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
    },
    extra=vol.PREVENT_EXTRA,
)
CONFIG_SCHEMA: Final = SCHEMA_USER.extend(
    {
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT): vol.All(
            cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)
        ),
    },
    extra=vol.PREVENT_EXTRA,
)


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Evohome."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._broker: EvoBroker | None = None

        self._username: str | None = None
        self._password: str | None = None
        self._loc_idx: str | None = None

        self._errors: dict[str, str] = {}

    async def _validate_step_user_credentials(self) -> bool:
        # if self._broker is None:
        #     self._broker = EvoBroker(self.hass)

        # self._broker.login(self._username, self._password)

        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by a user."""

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            return await self.async_step_location_idx(user_input)

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_USER, errors=self._errors
        )

    async def async_step_location_idx(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by a user."""

        if user_input and user_input.get(CONF_LOCATION_IDX) is not None:
            self._loc_idx = user_input[CONF_LOCATION_IDX]

            data = {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_LOCATION_IDX: self._loc_idx,
            }

            return self.async_create_entry(title=TITLE, data=data)

        return self.async_show_form(
            step_id="location_idx", data_schema=SCHEMA_LOC_IDX, errors=self._errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        data = import_data.copy()

        scan_interval: timedelta = data.pop(CONF_SCAN_INTERVAL)
        data[CONF_SCAN_INTERVAL] = int(scan_interval.total_seconds())

        return self.async_create_entry(title=TITLE, data=data)
