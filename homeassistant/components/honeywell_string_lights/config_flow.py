"""Config flow for the Honeywell String Lights integration."""

from __future__ import annotations

from typing import Any

from rf_protocols import RadioFrequencyCommand
import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import CONF_TRANSMITTER, DOMAIN
from .light import COMMANDS


class HoneywellStringLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Honeywell String Lights."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        sample_command: RadioFrequencyCommand = await self.hass.async_add_executor_job(
            COMMANDS.load_command, "turn_on"
        )
        try:
            transmitters = async_get_transmitters(
                self.hass, sample_command.frequency, sample_command.modulation
            )
        except HomeAssistantError:
            return self.async_abort(reason="no_transmitters")

        if not transmitters:
            return self.async_abort(reason="no_compatible_transmitters")

        if user_input is not None:
            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(user_input[CONF_TRANSMITTER])
            assert entity_entry is not None
            await self.async_set_unique_id(entity_entry.id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Honeywell String Lights",
                data={CONF_TRANSMITTER: entity_entry.id},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                        selector.EntitySelectorConfig(include_entities=transmitters),
                    ),
                }
            ),
        )
