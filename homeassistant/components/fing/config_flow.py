"""Config flow file."""

import asyncio
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN
from .fing_api.fing import Fing


def _get_data_schema(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> vol.Schema:
    """Get a schema with default values."""

    if config_entry is None:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default="Fing Agent"): str,
                vol.Required(AGENT_IP): str,
                vol.Required(AGENT_PORT, default="49090"): str,
                vol.Required(AGENT_KEY): str,
            }
        )

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=config_entry.data.get(CONF_NAME)): str,
            vol.Required(AGENT_IP, default=config_entry.data.get(AGENT_IP)): str,
            vol.Required(AGENT_PORT, default=config_entry.data.get(AGENT_PORT)): str,
            vol.Required(AGENT_KEY, default=config_entry.data.get(AGENT_KEY)): str,
        }
    )


async def _verify_connection(user_input: dict[str, Any]) -> bool:
    """Verify the user data."""
    fing_api = Fing(user_input[AGENT_IP], user_input[AGENT_PORT], user_input[AGENT_KEY])
    response = await fing_api.get_devices()
    return response.network_id is not None


class FingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fing config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    _verify_connection_task: asyncio.Task | None = None
    _user_input: dict[str, Any] | None = None
    _exception: BaseException | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up user step."""
        return self.async_show_form(
            step_id="verify",
            data_schema=_get_data_schema(self.hass),
        )

    async def async_step_verify(self, user_input=None) -> ConfigFlowResult:
        """Verify connection step."""
        if user_input is None and self._user_input:
            return self.async_abort(reason="Empty user input")

        if not self._verify_connection_task:
            self._user_input = user_input
            self._verify_connection_task = self.hass.async_create_task(
                _verify_connection(user_input=user_input)
            )
        if not self._verify_connection_task.done():
            self.async_show_progress(
                step_id="verify",
                progress_action="Verifying connection...",
                progress_task=self._verify_connection_task,
            )

        try:
            await self._verify_connection_task
            if self._verify_connection_task.exception() is not None:
                self._exception = self._verify_connection_task.exception()
            elif self._verify_connection_task.result() is False:
                self._exception = Exception(
                    "Network ID parameter is empty. Use the latest API."
                )
            else:
                return self.async_show_progress_done(next_step_id="task_completed")

            return self.async_show_progress_done(next_step_id="task_failed")
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            httpx.CookieConflict,
            httpx.StreamError,
            Exception,
        ) as exception:
            self._exception = exception
        finally:
            self._verify_connection_task = None

        return self.async_show_progress_done(next_step_id="task_failed")

    async def async_step_task_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Last step."""
        errors: dict[str, str] = {}
        if self._exception is None:
            errors["base"] = "Connection verification raised an unknown exception."
        elif isinstance(self._exception, httpx.HTTPError):
            errors["base"] = f"HTTP exception -> Args: {self._exception.args}"
        elif isinstance(self._exception, httpx.InvalidURL):
            errors["base"] = f"Invalid URL exception -> Args: {self._exception.args}"
        elif isinstance(self._exception, httpx.CookieConflict):
            errors["base"] = f"CookieConflict exception -> Args: {self._exception.args}"
        elif isinstance(self._exception, httpx.StreamError):
            errors["base"] = f"Stream error exception -> Args: {self._exception.args}"
        else:
            errors["base"] = f"Generic exception raised -> Args: {self._exception.args}"

        return self.async_show_form(
            step_id="verify",
            data_schema=_get_data_schema(self.hass),
            errors=errors,
        )

    async def async_step_task_completed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Last step."""
        if self._user_input is None:
            return self.async_show_form(
                step_id="verify",
                data_schema=_get_data_schema(self.hass),
            )

        return self.async_create_entry(
            title=self._user_input[CONF_NAME], data=self._user_input
        )

    # @staticmethod
    # @callback
    # def async_get_options_flow(
    #     config_entry: ConfigEntry,
    # ) -> OptionsFlow:
    #     """Get the options flow for Met."""
    #     return FingOptionsFlow(config_entry)


class FingOptionsFlow(OptionsFlowWithConfigEntry):
    """Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure options."""

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._config_entry, title=user_input[CONF_NAME], data=user_input
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(self.hass, config_entry=self._config_entry),
        )
