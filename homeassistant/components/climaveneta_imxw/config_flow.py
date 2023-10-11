"""Support for the Mitsubishi-Climaveneta iMXW fancoil series."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.modbus import (
    CONF_HUB,
    get_hub,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_MODBUS_HUB,
    DEFAULT_SERIAL_SLAVE_ID,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Climaveneta_imxw."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._hub: str
        self._slave_id: int | None = None
        self._enable_parameter_configuration = False
        self._name: str

        # Only used in reauth flows:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        errors = {}
        if user_input is not None:
            try:
                get_hub(self.hass, user_input[CONF_HUB])
            except ValueError:
                errors["hub"] = "invalid_modbus_hub"
            else:
                if user_input[CONF_SLAVE] < 0 or user_input[CONF_SLAVE] > 255:
                    errors["slave"] = "invalid_slave_id"

                if not errors:
                    self._hub = user_input[CONF_HUB]
                    self._slave_id = user_input[CONF_SLAVE]
                    self._name = user_input[CONF_NAME]

                    title = f"Climaveneta_IMXW {user_input[CONF_NAME]} at {user_input[CONF_HUB]}:{user_input[CONF_SLAVE]}"
                    return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HUB, default=str(DEFAULT_MODBUS_HUB)): str,
                vol.Required(
                    CONF_SLAVE, default=int(DEFAULT_SERIAL_SLAVE_ID)
                ): vol.Range(min=0, max=255),
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="setup_serial",
            data_schema=schema,
            errors=errors,
        )
