"""Config flow for PECO Outage Counter integration."""
from __future__ import annotations

import asyncio
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

    meter_verification: bool = False
    meter_data: dict[str, str] = {}
    meter_error: dict[str, str] = {}

    async def _verify_meter(self, phone_number: str) -> None:
        """Verify if the meter is compatible."""

        api = PecoOutageApi()

        try:
            await api.meter_check(phone_number)
        except ValueError as err:
            self.meter_error = {"phone_number": "invalid_phone_number", "type": "error"}
            _LOGGER.exception(err)
        except IncompatibleMeterError as err:
            self.meter_error = {"phone_number": "incompatible_meter", "type": "abort"}
            _LOGGER.exception(err)
        except UnresponsiveMeterError as err:
            self.meter_error = {"phone_number": "unresponsive_meter", "type": "error"}
            _LOGGER.exception(err)
        except HttpError as err:
            self.meter_error = {"phone_number": "http_error", "type": "error"}
            _LOGGER.exception(err)

        self.hass.async_create_task(
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self.meter_verification is True:
            if "phone_number" in self.meter_error:
                if self.meter_error["phone_number"] == "invalid_phone_number":
                    await asyncio.sleep(
                        0.1
                    )  # If I don't have this here, it will be stuck on the loading symbol
            return self.async_show_progress_done(next_step_id="finish_smart_meter")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        county = user_input[CONF_COUNTY]
        phone_number = user_input[CONF_PHONE_NUMBER]

        if phone_number is None:
            return self.async_create_entry(
                title=user_input[CONF_COUNTY].capitalize(), data=user_input
            )

        await self.async_set_unique_id(f"{county}-{phone_number}")
        self._abort_if_unique_id_configured()

        self.meter_verification = True

        if self.meter_error is not None:
            self.meter_error = (
                {}
            )  # Clear any previous errors, since the user may have corrected them

        self.hass.async_create_task(self._verify_meter(phone_number))

        self.meter_data = user_input

        return self.async_show_progress(
            step_id="user",
            progress_action="verifying_meter",
        )

    async def async_step_finish_smart_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the finish smart meter step."""
        if "phone_number" in self.meter_error:
            if self.meter_error["type"] == "error":
                self.meter_verification = False
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
