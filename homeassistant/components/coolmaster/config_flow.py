"""Config flow to configure Coolmaster."""

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


async def _validate_connection(host: str, port: int, send_wakeup_prompt: bool) -> bool:
    cool = CoolMasterNet(host, port, send_initial_line_feed=send_wakeup_prompt)
    units = await cool.status()
    return bool(units)


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
                CONF_SUPPORTED_MODES: [
                    mode for mode in AVAILABLE_MODES if data.get(mode)
                ],
                CONF_SWING_SUPPORT: data[CONF_SWING_SUPPORT],
                CONF_SEND_WAKEUP_PROMPT: more_options.get(
                    CONF_SEND_WAKEUP_PROMPT, False
                ),
            },
        )

    async def _async_validate_input(
        self, user_input: dict[str, Any], port: int
    ) -> dict[str, str]:
        """Check we can still talk to the bridge and that it reports units."""
        more_options = user_input.get(CONF_MORE_OPTIONS, {})
        errors: dict[str, str] = {}
        try:
            has_units = await _validate_connection(
                user_input[CONF_HOST],
                port,
                more_options.get(CONF_SEND_WAKEUP_PROMPT, False),
            )
        except OSError:
            errors["base"] = "cannot_connect"
        else:
            if not has_units:
                errors["base"] = "no_units"
        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        if errors := await self._async_validate_input(user_input, DEFAULT_PORT):
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self._async_get_entry(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        entry_data = reconfigure_entry.data
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            more_options = user_input.get(CONF_MORE_OPTIONS, {})
            # The port is not part of the form, so keep validating the stored one.
            if not (
                errors := await self._async_validate_input(
                    user_input, entry_data[CONF_PORT]
                )
            ):
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=user_input[CONF_HOST],
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SUPPORTED_MODES: [
                            mode for mode in AVAILABLE_MODES if user_input.get(mode)
                        ],
                        CONF_SWING_SUPPORT: user_input[CONF_SWING_SUPPORT],
                        CONF_SEND_WAKEUP_PROMPT: more_options.get(
                            CONF_SEND_WAKEUP_PROMPT, False
                        ),
                    },
                )

        supported_modes = entry_data.get(CONF_SUPPORTED_MODES, AVAILABLE_MODES)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA,
                user_input
                or {
                    CONF_HOST: entry_data[CONF_HOST],
                    **{mode: mode in supported_modes for mode in AVAILABLE_MODES},
                    CONF_SWING_SUPPORT: entry_data.get(CONF_SWING_SUPPORT, False),
                    CONF_MORE_OPTIONS: {
                        CONF_SEND_WAKEUP_PROMPT: entry_data.get(
                            CONF_SEND_WAKEUP_PROMPT, False
                        )
                    },
                },
            ),
            errors=errors,
        )
