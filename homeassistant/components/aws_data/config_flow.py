"""Config flow for AWS Data integration."""

from __future__ import annotations

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
    CONST_GENERAL_REGION,
    CONST_GENERIC_ID,
    CONST_REGION_STR,
    CONST_SCAN_REGIONS,
    DOMAIN,
    USER_INPUT_DATA,
    USER_INPUT_ID,
    USER_INPUT_REGIONS,
    USER_INPUT_SERVICES,
)

_LOGGER = logging.getLogger(__name__)

services = SelectSelector(
    SelectSelectorConfig(
        {
            "options": ["ec2", "ebs", "s3"],
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
    USER_DATA: dict[str, dict] = {}

    def _error(self, result: dict) -> dict:
        """Handle Errors."""
        errors: dict[str, str] = {}
        if "Error" in result:
            errors["base"] = "unknown"
            if result["Error"]["Code"] == "AccessDeniedException":
                errors["base"] = "access_denied"
                return errors
            if result["Error"]["Code"] == "InvalidClientTokenId":
                errors["base"] = "invalid_auth"
                return errors

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            awsAPI = AWSDataClient(
                user_input[CONST_AWS_KEY], user_input[CONST_AWS_SECRET]
            )
            result = await awsAPI.serviceCall(serviceName="sts", operation="id")

            errors = self._error(result=result)
            self.USER_DATA = {}
            if not errors:
                if DOMAIN not in self.USER_DATA:
                    self.USER_DATA[DOMAIN] = {}

                keyHash = sha256(user_input[CONST_AWS_KEY].encode("utf-8")).hexdigest()
                self.USER_DATA[DOMAIN][USER_INPUT_ID] = keyHash
                if USER_INPUT_DATA not in self.USER_DATA[DOMAIN]:
                    self.USER_DATA[DOMAIN][USER_INPUT_DATA] = {}

                self.USER_DATA[DOMAIN][USER_INPUT_DATA][USER_INPUT_ID] = keyHash

                self.USER_DATA[DOMAIN][USER_INPUT_DATA][CONST_ACCOUNT_ID] = ""
                if "Account" in result:
                    self.USER_DATA[DOMAIN][USER_INPUT_DATA][CONST_ACCOUNT_ID] = result[
                        "Account"
                    ]

                if API_DATA not in self.USER_DATA[DOMAIN]:
                    self.USER_DATA[DOMAIN][API_DATA] = awsAPI

                return await self.async_step_service()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_service(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Service And Region Step."""
        errors: dict[str, str] = {}

        ac_id = None

        if USER_INPUT_ID in self.USER_DATA[DOMAIN][USER_INPUT_DATA]:
            ac_id = self.USER_DATA[DOMAIN][USER_INPUT_DATA][USER_INPUT_ID]

        if user_input is not None:
            entryID = f"{DOMAIN}_"
            if ac_id is None:
                entryID += CONST_GENERIC_ID
            else:
                entryID += ac_id

            self.USER_DATA[DOMAIN][USER_INPUT_DATA][CONST_SCAN_REGIONS] = user_input[
                CONST_SCAN_REGIONS
            ]

            user_title = ""
            if CONST_AWS_REGION in user_input:
                user_title = "all"
                self.USER_DATA[DOMAIN][USER_INPUT_DATA][USER_INPUT_REGIONS] = (
                    user_input[CONST_AWS_REGION]
                )
            elif CONST_REGION_STR in user_input:
                user_title = user_input[CONST_REGION_STR]
                self.USER_DATA[DOMAIN][USER_INPUT_DATA][USER_INPUT_REGIONS] = (
                    user_input[CONST_REGION_STR]
                )

            self.USER_DATA[DOMAIN][USER_INPUT_DATA][USER_INPUT_SERVICES] = user_input[
                CONST_AWS_SERVICES
            ]

            # To Enable Serialization, removing api class
            self.USER_DATA[DOMAIN][API_DATA] = None

            currentEntries = self._async_current_entries()
            for entr in currentEntries:
                if entr.unique_id == entryID:
                    return self.async_update_reload_and_abort(
                        entr, unique_id=entryID, title=user_title, data=self.USER_DATA
                    )

            await self.async_set_unique_id(entryID)
            return self.async_create_entry(title=user_title, data=self.USER_DATA)

        regions = {}
        if ac_id is not None:
            awsAPI = self.USER_DATA[DOMAIN][API_DATA]
            regions = await awsAPI.serviceCall(
                serviceName="account", operation="list_regions"
            )
            errors = self._error(result=regions)

        service_schema = await self.build_service_schema(regions=regions, errors=errors)
        return self.async_show_form(
            step_id="service", data_schema=service_schema, errors=errors
        )

    async def build_service_schema(
        self, regions: dict | None = None, errors: dict | None = None
    ) -> vol.Schema:
        """Build Service Step Window Based On Available Region List."""

        region_choice = CONST_AWS_REGION
        region_schema: type[str] | SelectSelector
        if errors or not regions:
            region_schema = vol.basestring
        else:
            region_choice = CONST_REGION_STR
            reg_list = [items["RegionName"] for items in regions["Regions"]]
            region_schema = SelectSelector(
                SelectSelectorConfig(
                    {
                        "options": reg_list,
                        "mode": SelectSelectorMode("dropdown"),
                        "multiple": True,
                    }
                )
            )

        return vol.Schema(
            {
                vol.Optional(region_choice): region_schema,
                vol.Required(
                    CONST_AWS_SERVICES,
                ): services,
                vol.Optional(CONST_SCAN_REGIONS, default=False): BooleanSelector(),
                vol.Optional(CONST_GENERAL_REGION, default=False): BooleanSelector(),
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AccessDenied(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
