"""Config flow for PECO Outage Counter integration."""
from __future__ import annotations

import asyncio
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

from .const import CONF_COUNTY, CONF_PHONE_NUMBER, COUNTY_LIST, DOMAIN, LOGGER

STEP_OUTAGE_COUNTER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTY): vol.In(COUNTY_LIST),
    }
)
STEP_SMART_METER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE_NUMBER): cv.string,
    }
)


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
        except ValueError:
            self.meter_error = {"base": "invalid_phone_number", "type": "error"}
        except IncompatibleMeterError:
            self.meter_error = {"base": "incompatible_meter", "type": "abort"}
        except UnresponsiveMeterError:
            self.meter_error = {"base": "unresponsive_meter", "type": "error"}
        except HttpError:
            self.meter_error = {"base": "http_error", "type": "error"}

        LOGGER.debug("verify meter done :)")
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user", menu_options=["outage_counter", "smart_meter"]
        )

    async def async_step_outage_counter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the outage counter step."""
        if user_input is None:
            return self.async_show_form(
                step_id="outage_counter",
                data_schema=STEP_OUTAGE_COUNTER_DATA_SCHEMA,
            )

        county = user_input[CONF_COUNTY]

        await self.async_set_unique_id(county)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{county.capitalize()} Outage Count", data=user_input
        )

    async def async_step_smart_meter(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the smart meter step."""
        if self.meter_verification is True:
            LOGGER.debug(self.meter_error)
            LOGGER.debug("hi")
            if self.meter_error is not None:
                if self.meter_error["base"] == "invalid_phone_number":
                    await asyncio.sleep(
                        0.1
                    )  # If I don't have this here, it will be stuck on the loading symbol
            return self.async_show_progress_done(next_step_id="finish_smart_meter")

        if not user_input:
            return self.async_show_form(
                step_id="smart_meter",
                data_schema=STEP_SMART_METER_DATA_SCHEMA,
            )

        phone_number = user_input[CONF_PHONE_NUMBER]

        await self.async_set_unique_id(phone_number)
        self._abort_if_unique_id_configured()

        self.meter_verification = True

        if self.meter_error is not None:
            self.meter_error = (
                {}
            )  # Clear any previous errors, since the user may have corrected them

        self.hass.async_create_task(self._verify_meter(phone_number))

        self.meter_data = user_input

        return self.async_show_progress(
            step_id="smart_meter",
            progress_action="verifying_meter",
        )

    async def async_step_finish_smart_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the finish smart meter step."""
        LOGGER.debug(self.meter_error)
        LOGGER.debug("e.e.e.e.e.e.e.e")
        if self.meter_error:
            LOGGER.debug("woah an error")
            if self.meter_error["type"] == "error":
                LOGGER.debug("error detected")
                self.meter_verification = False
                return self.async_show_form(
                    step_id="smart_meter",
                    data_schema=STEP_SMART_METER_DATA_SCHEMA,
                    errors={"base": self.meter_error["base"]},
                )

            return self.async_abort(reason=self.meter_error["base"])

        return self.async_create_entry(
            title=f"{self.meter_data[CONF_PHONE_NUMBER]} Smart Meter",
            data=self.meter_data,
        )
