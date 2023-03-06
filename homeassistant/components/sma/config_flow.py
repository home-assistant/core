"""Config flow for the sma integration."""
from __future__ import annotations

import logging
from typing import Any

import pysma
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_HOST,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_GROUP, DEFAULT_LANGUAGE, DOMAIN, GROUPS

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])

    protocol = "https" if data[CONF_SSL] else "http"
    url = f"{protocol}://{data[CONF_HOST]}"

    sma = pysma.SMA(session, url, data[CONF_PASSWORD], group=data[CONF_GROUP])

    # new_session raises SmaAuthenticationException on failure
    await sma.new_session()
    device_info = await sma.device_info()
    await sma.close_session()

    return device_info


class SmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data = {
            CONF_HOST: vol.UNDEFINED,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_GROUP: GROUPS[0],
            CONF_PASSWORD: vol.UNDEFINED,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SmaOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step in config flow."""
        errors = {}
        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_SSL] = user_input[CONF_SSL]
            self._data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            self._data[CONF_GROUP] = user_input[CONF_GROUP]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            try:
                device_info = await validate_input(self.hass, user_input)
            except pysma.exceptions.SmaConnectionException:
                errors["base"] = "cannot_connect"
            except pysma.exceptions.SmaAuthenticationException:
                errors["base"] = "invalid_auth"
            except pysma.exceptions.SmaReadException:
                errors["base"] = "cannot_retrieve_device_info"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(device_info["serial"])
                self._abort_if_unique_id_configured(updates=self._data)
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )


class SmaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a sma options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    def _get_option_schema_lang(self) -> vol.Schema:
        """Get option schema for entering SMA language."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_LANGUAGE,
                    msg="SMA language",
                    default=DEFAULT_LANGUAGE,
                    description={
                        "suggested_value": self.config_entry.options.get(CONF_LANGUAGE)
                    },
                ): str
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        option_schema_lang = self._get_option_schema_lang()

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=option_schema_lang,
                errors={},
            )

        return self.async_create_entry(
            title="", data={CONF_LANGUAGE: user_input.get(CONF_LANGUAGE)}
        )
