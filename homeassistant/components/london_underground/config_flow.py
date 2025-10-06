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
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LINE, DEFAULT_LINES, DOMAIN, TUBE_LINES

_LOGGER = logging.getLogger(__name__)


class LondonUndergroundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for London Underground."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        _: ConfigEntry,
    ) -> LondonUndergroundOptionsFlow:
        """Get the options flow for this handler."""
        return LondonUndergroundOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            data = TubeData(session)
            try:
                async with asyncio.timeout(10):
                    await data.update()
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "cannot_connect"
            else:
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

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        session = async_get_clientsession(self.hass)
        data = TubeData(session)
        try:
            async with asyncio.timeout(10):
                await data.update()
        except Exception as ex:
            _LOGGER.exception(
                "Unexpected error trying to connect before importing config, aborting import "
            )
            raise ex from None
        _LOGGER.warning(
            "Importing London Underground config from configuration.yaml: %s",
            import_data,
        )
        # Extract lines from the sensor platform config
        lines = import_data.get(CONF_LINE, DEFAULT_LINES)
        return await self.async_step_user({CONF_LINE: lines})


class LondonUndergroundOptionsFlow(OptionsFlowWithReload):
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
