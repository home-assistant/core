"""Config flow for PECO Outage Counter integration."""
from __future__ import annotations

import logging
from typing import Any

from peco import (
    HttpError,
    IncompatibleMeterError,
    PecoOutageApi,
    UnresponsiveMeterError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_COUNTY, CONF_PHONE_NUMBER, COUNTY_LIST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTY): vol.In(COUNTY_LIST),
        vol.Optional(CONF_PHONE_NUMBER): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PECO Outage Counter."""

    VERSION = 1

    meter_data: dict[str, str] = {}
    meter_error: dict[str, str] = {}

    async def _verify_meter(self, phone_number: str) -> None:
        """Verify if the meter is compatible."""

        api = PecoOutageApi()

        try:
            await api.meter_check(phone_number)
        except ValueError:
            self.meter_error = {"phone_number": "invalid_phone_number", "type": "error"}
        except IncompatibleMeterError:
            self.meter_error = {"phone_number": "incompatible_meter", "type": "abort"}
        except UnresponsiveMeterError:
            self.meter_error = {"phone_number": "unresponsive_meter", "type": "error"}
        except HttpError:
            self.meter_error = {"phone_number": "http_error", "type": "error"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        county = user_input[CONF_COUNTY]

        if CONF_PHONE_NUMBER not in user_input:
            await self.async_set_unique_id(county)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{user_input[CONF_COUNTY].capitalize()} Outage Count",
                data=user_input,
            )

        phone_number = user_input[CONF_PHONE_NUMBER]

        await self.async_set_unique_id(f"{county}-{phone_number}")
        self._abort_if_unique_id_configured()

        if self.meter_error is not None:
            # Clear any previous errors, since the user may have corrected them
            self.meter_error = {}

        await self._verify_meter(phone_number)

        self.meter_data = user_input

        return await self.async_step_finish_smart_meter()

    async def async_step_finish_smart_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the finish smart meter step."""
        if "phone_number" in self.meter_error:
            if self.meter_error["type"] == "error":
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"phone_number": self.meter_error["phone_number"]},
                )

            return self.async_abort(reason=self.meter_error["phone_number"])

        return self.async_create_entry(
            title=f"{self.meter_data[CONF_COUNTY].capitalize()} - {self.meter_data[CONF_PHONE_NUMBER]}",
            data=self.meter_data,
        )
