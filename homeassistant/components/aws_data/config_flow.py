"""Config flow for AWS Data integration."""

from __future__ import annotations

<<<<<<< HEAD
=======
from collections.abc import Sequence
>>>>>>> 833ac3afab (Setup Coordinates)
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
<<<<<<< HEAD
=======
    CONST_ERRORS,
>>>>>>> 833ac3afab (Setup Coordinates)
    CONST_GENERAL_REGION,
    CONST_GENERIC_ID,
    CONST_REGION_STR,
    CONST_SCAN_REGIONS,
    DOMAIN,
<<<<<<< HEAD
    USER_INPUT_DATA,
    USER_INPUT_ID,
    USER_INPUT_REGIONS,
=======
    SUPPORTED_SERVICES,
    USER_INPUT_DATA,
    USER_INPUT_ID,
    USER_INPUT_REGIONS,
    USER_INPUT_SECRET,
>>>>>>> 833ac3afab (Setup Coordinates)
    USER_INPUT_SERVICES,
)

_LOGGER = logging.getLogger(__name__)

services = SelectSelector(
    SelectSelectorConfig(
        {
<<<<<<< HEAD
            "options": ["ec2", "ebs", "s3"],
=======
            "options": SUPPORTED_SERVICES,
>>>>>>> 833ac3afab (Setup Coordinates)
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
<<<<<<< HEAD
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
=======
    USER_DATA: dict[str, Any] = {}
    REGION_DATA: dict[str, Any] = {}
>>>>>>> 833ac3afab (Setup Coordinates)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
<<<<<<< HEAD
            awsAPI = AWSDataClient(
=======
            awsAPI: AWSDataClient = AWSDataClient(
>>>>>>> 833ac3afab (Setup Coordinates)
                user_input[CONST_AWS_KEY], user_input[CONST_AWS_SECRET]
            )
            result = await awsAPI.serviceCall(serviceName="sts", operation="id")

<<<<<<< HEAD
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
=======
            errors = AWSDataClient.error(result=result)
            self.USER_DATA: dict[str, Any] = {}
            if not errors:
                if USER_INPUT_DATA not in self.USER_DATA:
                    self.USER_DATA[USER_INPUT_DATA] = {}

                self.USER_DATA[USER_INPUT_DATA][USER_INPUT_ID] = user_input[
                    CONST_AWS_KEY
                ]
                self.USER_DATA[USER_INPUT_DATA][USER_INPUT_SECRET] = user_input[
                    CONST_AWS_SECRET
                ]
                self.USER_DATA[USER_INPUT_DATA][CONST_ACCOUNT_ID] = None
                if "Account" in result:
                    self.USER_DATA[USER_INPUT_DATA][CONST_ACCOUNT_ID] = result[
                        "Account"
                    ]

                if API_DATA not in self.USER_DATA:
                    self.USER_DATA[API_DATA] = awsAPI
>>>>>>> 833ac3afab (Setup Coordinates)

                return await self.async_step_service()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_service(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Service And Region Step."""
        errors: dict[str, str] = {}

<<<<<<< HEAD
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
=======
        user_id = CONST_GENERIC_ID
        if USER_INPUT_ID in self.USER_DATA[USER_INPUT_DATA]:
            user_id = self.USER_DATA[USER_INPUT_DATA][USER_INPUT_ID]

        account_id = CONST_GENERIC_ID
        if CONST_ACCOUNT_ID in self.USER_DATA[USER_INPUT_DATA]:
            account_id = self.USER_DATA[USER_INPUT_DATA][CONST_ACCOUNT_ID]

        awsAPI: AWSDataClient = self.USER_DATA[API_DATA]
        if user_input is None:
            temp_region = await awsAPI.serviceCall(
                serviceName="account", operation="list_regions"
            )
            error_validate = AWSDataClient.error(result=temp_region)
            self.REGION_DATA[CONST_AWS_REGION] = []
            if not error_validate and "Regions" in temp_region:
                self.REGION_DATA[CONST_AWS_REGION] = [
                    item["RegionName"] for item in temp_region["Regions"]
                ]

            self.REGION_DATA[CONST_ERRORS] = error_validate

        if user_input is not None:
            keyHash = sha256(user_id.encode("utf-8")).hexdigest()
            entryID = f"{DOMAIN}_{keyHash}"
            self.USER_DATA[USER_INPUT_DATA][USER_INPUT_SERVICES] = user_input[
                CONST_AWS_SERVICES
            ]

            region_choice = []
            entry_title = f"AWS Account {account_id}"
            scan_all = (
                user_input[CONST_SCAN_REGIONS]
                if not self.REGION_DATA[CONST_ERRORS]
                else False
            )
            self.USER_DATA[USER_INPUT_DATA][CONST_SCAN_REGIONS] = scan_all
            if scan_all:
                region_choice = self.REGION_DATA[CONST_AWS_REGION]
                entry_title += ": All Regions"
            else:
                if CONST_AWS_REGION in user_input:
                    region_choice = user_input[CONST_AWS_REGION]
                elif CONST_REGION_STR in user_input:
                    region_choice = user_input[CONST_REGION_STR].split(",")
                entry_title += f" - Regions: {region_choice}"
            self.USER_DATA[USER_INPUT_DATA][USER_INPUT_REGIONS] = region_choice

            if region_choice or (self.REGION_DATA[CONST_AWS_REGION] and scan_all):
                # To Enable Serialization, removing api class, will be added later in hass.data
                self.USER_DATA[API_DATA] = None

                currentEntries = self._async_current_entries()
                for entr in currentEntries:
                    if entr.unique_id == entryID:
                        return self.async_update_reload_and_abort(
                            entr,
                            unique_id=entryID,
                            title=entry_title,
                            data=self.USER_DATA,
                            reason="Updating Existing Entry",
                        )

                await self.async_set_unique_id(entryID)
                return self.async_create_entry(title=entry_title, data=self.USER_DATA)

        service_schema = await self.build_service_schema(
            regions=self.REGION_DATA[CONST_AWS_REGION],
            errors=self.REGION_DATA[CONST_ERRORS],
        )
>>>>>>> 833ac3afab (Setup Coordinates)
        return self.async_show_form(
            step_id="service", data_schema=service_schema, errors=errors
        )

    async def build_service_schema(
<<<<<<< HEAD
        self, regions: dict | None = None, errors: dict | None = None
=======
        self, regions: Sequence[str], errors: dict | None = None
>>>>>>> 833ac3afab (Setup Coordinates)
    ) -> vol.Schema:
        """Build Service Step Window Based On Available Region List."""

        region_choice = CONST_AWS_REGION
        region_schema: type[str] | SelectSelector
<<<<<<< HEAD
        if errors or not regions:
            region_schema = vol.basestring
        else:
            region_choice = CONST_REGION_STR
            reg_list = [items["RegionName"] for items in regions["Regions"]]
            region_schema = SelectSelector(
                SelectSelectorConfig(
                    {
                        "options": reg_list,
=======
        if errors:
            region_schema = vol.basestring
            region_choice = CONST_REGION_STR
        else:
            region_schema = SelectSelector(
                SelectSelectorConfig(
                    {
                        "options": regions,
>>>>>>> 833ac3afab (Setup Coordinates)
                        "mode": SelectSelectorMode("dropdown"),
                        "multiple": True,
                    }
                )
            )

        return vol.Schema(
            {
                vol.Optional(region_choice): region_schema,
<<<<<<< HEAD
                vol.Required(
                    CONST_AWS_SERVICES,
                ): services,
=======
                vol.Required(CONST_AWS_SERVICES): services,
>>>>>>> 833ac3afab (Setup Coordinates)
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
