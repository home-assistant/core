"""Config flow for AWS Data integration."""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .client import AWSDataClient
from .const import (
    API_DATA,
    CONST_ACCOUNT_ID,
    CONST_AWS_KEY,
    CONST_AWS_REGION,
    CONST_AWS_SECRET,
    CONST_AWS_SERVICES,
    CONST_CE_SELECT,
    CONST_GENERIC_ID,
    CONST_SCAN_REGIONS,
    DOMAIN,
    SUPPORTED_SERVICES,
    U_ID,
    U_REGIONS,
    U_SECRET,
    U_SERVICES,
    USER_INPUT,
)

_LOGGER = logging.getLogger(__name__)

services = SelectSelector(
    SelectSelectorConfig(
        {
            "options": SUPPORTED_SERVICES,
            "multiple": True,
            "mode": SelectSelectorMode("dropdown"),
        }
    )
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONST_AWS_KEY): str, vol.Required(CONST_AWS_SECRET): str}
)


class AWSDataConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AWS Data."""

    VERSION = 1
    USER_DATA: dict[str, Any] = {}
    REGION_DATA: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        self.USER_DATA: dict[str, Any] = {}
        self.USER_DATA[USER_INPUT] = {}
        if user_input is not None:
            awsAPI: AWSDataClient = AWSDataClient(
                user_input[CONST_AWS_KEY], user_input[CONST_AWS_SECRET]
            )
            result = await awsAPI.serviceCall(serviceName="sts", operation="id")
            errors = AWSDataClient.error(result=result)
            if not errors:
                self.USER_DATA[API_DATA] = awsAPI
                self.USER_DATA[USER_INPUT][U_ID] = user_input[CONST_AWS_KEY]
                self.USER_DATA[USER_INPUT][U_SECRET] = user_input[CONST_AWS_SECRET]
                self.USER_DATA[USER_INPUT][CONST_ACCOUNT_ID] = result.get(
                    "Account", CONST_GENERIC_ID
                )
                return await self.async_step_service()

        error_message = errors.get("message", "")
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"error_message": error_message},
        )

    async def async_step_service(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Service And Region Step."""

        errors: dict[str, str] = {}
        awsAPI: AWSDataClient = self.USER_DATA[API_DATA]
        if user_input is None:
            regions_list = await awsAPI.serviceCall(
                serviceName="account", operation="list_regions"
            )
            self.REGION_DATA[CONST_AWS_REGION] = [
                item["RegionName"] for item in regions_list.get("Regions", [])
            ]
            if not regions_list:
                errors = AWSDataClient.error(result=regions_list)
                error_message = errors.get("message", "unknown error")
                _LOGGER.warning("Region List is not Produced: %s", error_message)

        if user_input is not None:
            user_id = self.USER_DATA[USER_INPUT][U_ID]
            account_id = self.USER_DATA[USER_INPUT][CONST_ACCOUNT_ID]
            entryID = f"{DOMAIN}_{sha256(user_id.encode("utf-8")).hexdigest()}"
            region_input = user_input.get(CONST_AWS_REGION, [])
            scan_all = (
                user_input.get(CONST_SCAN_REGIONS, False)
                if self.REGION_DATA[CONST_AWS_REGION]
                else False
            )
            region_choice = (
                self.REGION_DATA[CONST_AWS_REGION]
                if scan_all
                else (
                    region_input
                    if not isinstance(region_input, str)
                    else region_input.split(",")
                )
            )

            self.USER_DATA[USER_INPUT][U_SERVICES] = user_input[CONST_AWS_SERVICES]
            self.USER_DATA[USER_INPUT][CONST_CE_SELECT] = user_input[CONST_CE_SELECT]
            self.USER_DATA[USER_INPUT][U_REGIONS] = region_choice
            self.USER_DATA[USER_INPUT][CONST_SCAN_REGIONS] = scan_all
            if (region_choice and user_input[CONST_AWS_SERVICES]) or user_input[
                CONST_CE_SELECT
            ]:
                self.USER_DATA[API_DATA] = None
                currentEntries = self._async_current_entries()
                for entr in currentEntries:
                    if entr.unique_id == entryID:
                        self.USER_DATA[USER_INPUT][U_REGIONS].extend(
                            reg
                            for reg in entr.data[USER_INPUT][U_REGIONS]
                            if reg not in self.USER_DATA[USER_INPUT][U_REGIONS]
                        )
                        self.USER_DATA[USER_INPUT][U_SERVICES].extend(
                            serv
                            for serv in entr.data[USER_INPUT][U_SERVICES]
                            if serv not in self.USER_DATA[USER_INPUT][U_SERVICES]
                        )
                        return self.async_update_reload_and_abort(
                            entr,
                            unique_id=entryID,
                            title=f"AWS Account {account_id}",
                            data=self.USER_DATA,
                            reason="Updating Existing Entry",
                        )
                await self.async_set_unique_id(entryID)
                return self.async_create_entry(
                    title=f"AWS Account {account_id}", data=self.USER_DATA
                )

        region_text = (
            "Separated by comma (,)"
            if not self.REGION_DATA[CONST_AWS_REGION]
            else "Choose multiples from list"
        )
        service_schema = await self.build_service_schema(
            regions=self.REGION_DATA[CONST_AWS_REGION],
        )
        return self.async_show_form(
            step_id="service",
            data_schema=service_schema,
            errors=errors,
            description_placeholders={"region_text": region_text},
        )

    async def build_service_schema(self, regions: Sequence[str]) -> vol.Schema:
        """Build Service Step Window Based On Available Region List."""

        region_schema: type[str] | SelectSelector
        if not regions:
            region_schema = vol.basestring
        else:
            region_schema = SelectSelector(
                SelectSelectorConfig(
                    {
                        "options": regions,
                        "mode": SelectSelectorMode("dropdown"),
                        "multiple": True,
                    }
                )
            )

        return vol.Schema(
            {
                vol.Optional(CONST_AWS_REGION): region_schema,
                vol.Required(CONST_AWS_SERVICES): services,
                vol.Optional(CONST_SCAN_REGIONS, default=False): BooleanSelector(),
                vol.Optional(CONST_CE_SELECT, default=False): BooleanSelector(),
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AccessDenied(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
