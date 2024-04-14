"""Config flow for Wemo."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, get_type_hints

import pywemo
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN
from .wemo_device import Options, OptionsValidationError


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    return bool(await hass.async_add_executor_job(pywemo.discover_devices))


class WemoFlow(DiscoveryFlowHandler, domain=DOMAIN):
    """Discovery flow with options for Wemo."""

    def __init__(self) -> None:
        """Init discovery flow."""
        super().__init__(DOMAIN, "Wemo", _async_has_devices)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return WemoOptionsFlow(config_entry)


class WemoOptionsFlow(OptionsFlow):
    """Options flow for the WeMo component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options for the WeMo component."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            try:
                Options(**user_input)
            except OptionsValidationError as err:
                errors = {err.field_key: err.error_key}
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema_for_options(Options(**self.config_entry.options)),
            errors=errors,
        )


def _schema_for_options(options: Options) -> vol.Schema:
    """Return the Voluptuous schema for the Options instance.

    All values are optional. The default value is set to the current value and
    the type hint is set to the value of the field type annotation.
    """
    return vol.Schema(
        {
            vol.Optional(
                field.name, default=getattr(options, field.name)
            ): get_type_hints(options)[field.name]
            for field in fields(options)
        }
    )
