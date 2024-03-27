"""Config flow for Switcher integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_TOKEN, DATA_DISCOVERY, DOMAIN
from .utils import async_discover_devices


class SwitcherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    def __init__(self) -> None:
        """Initialize flow."""
        self._token: str | None = None

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initiated by import."""
        if self._async_current_entries(True):
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Switcher", data={})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""

        if self._async_current_entries(True):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_get_data_schema(),
                errors={},
            )

        self._token = user_input.get(CONF_TOKEN, "")

        self.hass.data.setdefault(DOMAIN, {})
        if DATA_DISCOVERY not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][DATA_DISCOVERY] = self.hass.async_create_task(
                async_discover_devices()
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of the config flow."""
        discovered_devices = await self.hass.data[DOMAIN][DATA_DISCOVERY]

        if len(discovered_devices) == 0:
            self.hass.data[DOMAIN].pop(DATA_DISCOVERY)
            return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(
            title="Switcher",
            data={
                CONF_TOKEN: self._token,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for Switcher."""
        return SwitcherOptionsFlowHandler(config_entry)


class SwitcherOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Switcher component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the Switcher OptionsFlow."""
        self._config_entry = config_entry
        self._errors: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure options for Switcher."""

        if user_input is not None:
            # Update config entry with data from user input
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            )
            return self.async_create_entry(
                title=self._config_entry.title, data=user_input
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(config_entry=self._config_entry),
            errors=self._errors,
        )


def _get_data_schema(
    config_entry: config_entries.ConfigEntry | None = None,
) -> vol.Schema:
    """Get a schema with default values."""
    if config_entry is None:
        return vol.Schema(
            {
                vol.Optional(CONF_TOKEN): str,
            }
        )

    return vol.Schema(
        {
            vol.Optional(CONF_TOKEN, default=config_entry.data.get(CONF_TOKEN)): str,
        }
    )
