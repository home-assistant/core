"""Config flow for prayer_times integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .mawaqit_hub import MawaqitHub

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for prayer_times."""

    VERSION = 1
    config_flow_data: dict[str, str] = {}
    m_dict: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    "latitude",
                    default=(self.hass.states.get("zone.home").attributes["latitude"]),
                ): float,
                vol.Optional(
                    "longitude",
                    default=(self.hass.states.get("zone.home").attributes["longitude"]),
                ): float,
            }
        )

        _LOGGER.debug("User input: %s", user_input)
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            # info = await validate_input(self.hass, user_input)
            _LOGGER.info("Init MawaqitHub")
            mawaqit_connect = MawaqitHub(
                user_input["username"],
                user_input["password"],
                user_input["latitude"],
                user_input["longitude"],
                "",
                "",
            )

            _LOGGER.info("Validate auth")
            await self.hass.async_add_executor_job(mawaqit_connect.validate_auth)
            _LOGGER.info("Validate coordinates")
            await self.hass.async_add_executor_job(mawaqit_connect.validate_coordinates)
            _LOGGER.debug("Fetch API token")
            api_token = await self.hass.async_add_executor_job(
                mawaqit_connect.get_api_token, True
            )
            _LOGGER.debug(api_token)
            ConfigFlow.config_flow_data = {**user_input, **api_token}
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self.async_step_select_mosque()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_mosque(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step."""

        _LOGGER.info("Mosque selection step")
        _LOGGER.debug("Mosque input: %s", ConfigFlow.config_flow_data)

        mwqt_input = ConfigFlow.config_flow_data

        mawaqit_connect = MawaqitHub(
            mwqt_input["username"],
            mwqt_input["password"],
            mwqt_input["latitude"],
            mwqt_input["longitude"],
            mwqt_input["token"],
            "",
        )

        if user_input is None:
            try:
                await self.hass.async_add_executor_job(mawaqit_connect.validate_auth)
                mawaqit_mosque_list = await self.hass.async_add_executor_job(
                    mawaqit_connect.get_mosque_list
                )
            except Exception:
                raise CannotConnect

            _LOGGER.debug("Mosque list: %s", mawaqit_mosque_list)

            if mawaqit_mosque_list != []:
                for mosque_item in mawaqit_mosque_list:
                    ConfigFlow.m_dict[
                        str(mosque_item["id"]) + ": " + mosque_item["slug"]
                    ] = mosque_item

                STEP_MOSQ_DATA_SCHEMA = vol.Schema(
                    {vol.Required("mosque"): vol.In(ConfigFlow.m_dict.keys())}
                )

            else:
                return self.async_abort(reason="no_mosque")

            return self.async_show_form(
                step_id="select_mosque", data_schema=STEP_MOSQ_DATA_SCHEMA
            )

        else:
            _LOGGER.info("Mosque inputt: %s %s", user_input, ConfigFlow.m_dict)
            slim_m_list: dict[str, str] = {
                "comp_name": user_input["mosque"],
                "id": ConfigFlow.m_dict[user_input["mosque"]]["id"],
                "name": ConfigFlow.m_dict[user_input["mosque"]]["name"],
                "slug": ConfigFlow.m_dict[user_input["mosque"]]["slug"],
                "uuid": ConfigFlow.m_dict[user_input["mosque"]]["uuid"],
            }
            _LOGGER.debug("slim_m_list %s", slim_m_list)
            complete_data = {**ConfigFlow.config_flow_data, **slim_m_list}
            _LOGGER.debug("Selection: %s", complete_data)
            return self.async_create_entry(
                title=f'Mawaqit {ConfigFlow.m_dict[user_input["mosque"]]["slug"]}',
                data=complete_data,
            )

        errors = {}

        return self.async_show_form(
            step_id="select_mosque", data_schema=STEP_MOSQ_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
