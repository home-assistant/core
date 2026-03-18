"""Config flow for HiVi Speaker integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HIVISpeakerConfigFlow(ConfigFlow, domain=DOMAIN):
    """HIVI speaker configuration flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User step - configure integration."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="HiVi Speaker", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get options flow."""
        return HIVISpeakerOptionsFlow()


class HIVISpeakerOptionsFlow(config_entries.OptionsFlow):
    """Options flow - using confirmation switch."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        super().__init__()
        self.open_num = 0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show initial step of the options flow."""
        _LOGGER.debug("Entering initial step of options flow")
        self.open_num = 0
        if user_input is not None:
            if user_input.get("confirm_refresh"):
                domain_data = self.hass.data.get(DOMAIN, {}).get(
                    self.config_entry.entry_id, {}
                )
                device_manager = domain_data.get("device_manager")
                if device_manager is not None:
                    await device_manager.refresh_discovery()
                else:
                    _LOGGER.warning(
                        "Device manager not available; skipping refresh from options"
                    )
                return await self.async_step_success()

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_refresh", default=True): bool,
                }
            ),
        )

    async def async_step_success(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Success page."""
        _LOGGER.debug("Displaying success page")
        if self.open_num == 0:
            self.open_num += 1
            return self.async_show_form(
                step_id="success",
                data_schema=vol.Schema({}),
            )
        return self.async_create_entry(title="", data={})
