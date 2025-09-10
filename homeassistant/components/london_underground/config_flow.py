"""Config flow for London Underground integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from london_tube_status import TubeData
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LINE, DEFAULT_LINES, DOMAIN, TUBE_LINES

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant) -> bool:
    """Validate that we can connect to the TfL API."""
    session = async_get_clientsession(hass)
    data = TubeData(session)

    try:
        async with asyncio.timeout(10):
            await data.update()
            _LOGGER.debug("Validation call returned API data: %s", data.data)
    except Exception as error:
        raise CannotConnect from error
    else:
        return True


class LondonUndergroundOptionsFlow(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug(
                "Updating london underground with options flow user_input: %s",
                user_input,
            )
            return self.async_create_entry(
                title="",
                data={CONF_LINE: user_input[CONF_LINE]},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LINE,
                        default=self.config_entry.options.get(
                            CONF_LINE,
                            self.config_entry.data.get(CONF_LINE, DEFAULT_LINES),
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=TUBE_LINES,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )


class LondonUndergroundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for London Underground."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> LondonUndergroundOptionsFlow:
        """Get the options flow for this handler."""
        return LondonUndergroundOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                # Only allow a single instance
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="London Underground",
                    data={},
                    options={CONF_LINE: user_input.get(CONF_LINE, DEFAULT_LINES)},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LINE,
                        default=DEFAULT_LINES,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=TUBE_LINES,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
