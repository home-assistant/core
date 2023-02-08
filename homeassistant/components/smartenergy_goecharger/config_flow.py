"""go-e Charger Cloud config flow and options flow setup."""

import logging
import re
from typing import Any, Literal

from goechargerv2.goecharger import GoeChargerApi
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


def _get_config_values(data_input: dict) -> dict:
    data: dict = {}
    config: list[str] = [CONF_NAME, CONF_HOST, CONF_API_TOKEN, CONF_SCAN_INTERVAL]

    for config_name in config:
        data[config_name] = data_input.get(config_name)

    return data


def _get_config_schema(default_values: dict) -> dict:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default_values.get(CONF_NAME, None)): str,
            vol.Required(CONF_HOST, default=default_values.get(CONF_HOST, None)): str,
            vol.Required(
                CONF_API_TOKEN, default=default_values.get(CONF_API_TOKEN, None)
            ): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=default_values.get(CONF_SCAN_INTERVAL, 10),
            ): vol.All(vol.Coerce(int), vol.Range(10, 60000)),
        }
    )


def _validate_host(host: str) -> None:
    """
    Test with regex if the host.

    - starts with http(s)://
    - continues with words and dots
    - optionally ends with a port, e.g. :1234.
    """
    if re.search(r"^(?:http(s)?:\/\/)+[\w\-\.]+([:]{1}[\d]+)?$", host):
        return None

    raise ValueError("invalid_host")


async def _ping_host(hass: HomeAssistant, host: str, token: str) -> None:
    """Do a simple status request to check if the authentication works properly."""
    api: GoeChargerApi = GoeChargerApi(host, token, wait=True)

    try:
        await hass.async_add_executor_job(api.request_status)
    except Exception as exc:
        raise InvalidAuth from exc


async def _validate_user_input(hass: HomeAssistant, user_input: dict) -> dict:
    """Execute all types of validations. In case there is an error, set it to the error object."""
    errors: dict = {}

    try:
        _validate_host(user_input[CONF_HOST])
        await _ping_host(hass, user_input[CONF_HOST], user_input[CONF_API_TOKEN])
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except ValueError as exc:
        errors["base"] = str(exc)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return errors


class GoeChargerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the go-e Charger Cloud component."""

    VERSION: Literal[1] = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return GoeChargerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict = {}
        data_schema: dict = _get_config_schema({CONF_SCAN_INTERVAL: 10})

        if user_input is not None:
            errors = await _validate_user_input(self.hass, user_input)

            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            data_schema = _get_config_schema(
                {
                    CONF_NAME: user_input.get(CONF_NAME),
                    CONF_HOST: user_input.get(CONF_HOST),
                    CONF_API_TOKEN: user_input.get(CONF_API_TOKEN),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL),
                }
            )

            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, ""),
                    data=_get_config_values(user_input),
                    options=_get_config_values(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=None if errors == {} else errors,
        )


class GoeChargerOptionsFlowHandler(OptionsFlow):
    """Config flow options handler for the go-e Charger Cloud component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry: ConfigEntry = config_entry
        self.options: dict[str, Any] = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict = {}
        data_schema: dict = _get_config_schema(
            {
                CONF_NAME: self.config_entry.options.get(CONF_NAME),
                CONF_HOST: self.config_entry.options.get(CONF_HOST),
                CONF_API_TOKEN: self.config_entry.options.get(CONF_API_TOKEN),
                CONF_SCAN_INTERVAL: self.config_entry.options.get(CONF_SCAN_INTERVAL),
            }
        )

        if user_input is not None:
            errors = await _validate_user_input(self.hass, user_input)

            # set default values to the current so the user is still within the same context,
            # otherwise it makes each input empty
            data_schema = _get_config_schema(
                {
                    CONF_NAME: user_input.get(CONF_NAME),
                    CONF_HOST: user_input.get(CONF_HOST),
                    CONF_API_TOKEN: user_input.get(CONF_API_TOKEN),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL),
                }
            )

            if not errors:
                self.options.update(user_input)
                return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=None if errors == {} else errors,
        )
