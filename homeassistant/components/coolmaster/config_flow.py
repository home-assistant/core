"""Config flow to configure Coolmaster."""

from collections.abc import Mapping
from typing import Any, override

from pycoolmasternet_async import CoolMasterNet
import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import SectionConfig, section

from .const import (
    CONF_MORE_OPTIONS,
    CONF_SEND_WAKEUP_PROMPT,
    CONF_SUPPORTED_MODES,
    CONF_SWING_SUPPORT,
    DEFAULT_PORT,
    DOMAIN,
)

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
        vol.Required(CONF_MORE_OPTIONS): section(
            vol.Schema(
                {
                    vol.Required(CONF_SEND_WAKEUP_PROMPT, default=False): bool,
                }
            ),
            SectionConfig(collapsed=True),
        ),
    }
)


async def _validate_connection(host: str, send_wakeup_prompt: bool) -> bool:
    cool = CoolMasterNet(host, DEFAULT_PORT, send_initial_line_feed=send_wakeup_prompt)
    units = await cool.status()
    return bool(units)


def _supported_modes(user_input: Mapping[str, Any]) -> list[str]:
    """Collect the modes enabled in the form into the stored list."""
    return [mode for mode in AVAILABLE_MODES if user_input.get(mode)]


def _entry_data_as_form(data: Mapping[str, Any]) -> dict[str, Any]:
    """Map stored entry data onto the form, which uses a boolean per mode."""
    supported_modes = data.get(CONF_SUPPORTED_MODES, AVAILABLE_MODES)
    return {
        CONF_HOST: data[CONF_HOST],
        **{mode: mode in supported_modes for mode in AVAILABLE_MODES},
        CONF_SWING_SUPPORT: data.get(CONF_SWING_SUPPORT, False),
        CONF_MORE_OPTIONS: {
            CONF_SEND_WAKEUP_PROMPT: data.get(CONF_SEND_WAKEUP_PROMPT, False)
        },
    }


class CoolmasterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Coolmaster config flow."""

    VERSION = 1

    @callback
    def _async_get_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        more_options = data.get(CONF_MORE_OPTIONS, {})
        return self.async_create_entry(
            title=data[CONF_HOST],
            data={
                CONF_HOST: data[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_SUPPORTED_MODES: _supported_modes(data),
                CONF_SWING_SUPPORT: data[CONF_SWING_SUPPORT],
                CONF_SEND_WAKEUP_PROMPT: more_options.get(
                    CONF_SEND_WAKEUP_PROMPT, False
                ),
            },
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Check we can still talk to the bridge and that it reports units."""
        more_options = user_input.get(CONF_MORE_OPTIONS, {})
        errors: dict[str, str] = {}
        try:
            if not await _validate_connection(
                user_input[CONF_HOST],
                more_options.get(CONF_SEND_WAKEUP_PROMPT, False),
            ):
                errors["base"] = "no_units"
        except OSError:
            errors["base"] = "cannot_connect"
        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        if errors := await self._async_validate_input(user_input):
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self._async_get_entry(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self._async_validate_input(user_input)):
                more_options = user_input.get(CONF_MORE_OPTIONS, {})
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=user_input[CONF_HOST],
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SUPPORTED_MODES: _supported_modes(user_input),
                        CONF_SWING_SUPPORT: user_input[CONF_SWING_SUPPORT],
                        CONF_SEND_WAKEUP_PROMPT: more_options.get(
                            CONF_SEND_WAKEUP_PROMPT, False
                        ),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA,
                user_input or _entry_data_as_form(reconfigure_entry.data),
            ),
            errors=errors,
        )
