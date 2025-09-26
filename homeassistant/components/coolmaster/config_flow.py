"""Config flow to configure Coolmaster."""

from __future__ import annotations

from typing import Any

from pycoolmasternet_async import CoolMasterNet
import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import CONF_SUPPORTED_MODES, CONF_SWING_SUPPORT, DEFAULT_PORT, DOMAIN

AVAILABLE_MODES = [
    HVACMode.OFF.value,
    HVACMode.HEAT.value,
    HVACMode.COOL.value,
    HVACMode.DRY.value,
    HVACMode.HEAT_COOL.value,
    HVACMode.FAN_ONLY.value,
]

MODES_SCHEMA = {vol.Required(mode, default=True): bool for mode in AVAILABLE_MODES}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        **MODES_SCHEMA,
        vol.Required(CONF_SWING_SUPPORT, default=False): bool,
    }
)


async def _validate_connection(host: str) -> bool:
    cool = CoolMasterNet(host, DEFAULT_PORT)
    units = await cool.status()
    return bool(units)


class CoolmasterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Coolmaster config flow."""

    VERSION = 1

    @callback
    def _async_get_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        supported_modes = [
            key for (key, value) in data.items() if key in AVAILABLE_MODES and value
        ]
        return self.async_create_entry(
            title=data[CONF_HOST],
            data={
                CONF_HOST: data[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_SUPPORTED_MODES: supported_modes,
                CONF_SWING_SUPPORT: data[CONF_SWING_SUPPORT],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_HOST]

        try:
            result = await _validate_connection(host)
            if not result:
                errors["base"] = "no_units"
        except OSError:
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self._async_get_entry(user_input)
