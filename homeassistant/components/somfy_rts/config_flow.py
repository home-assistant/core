"""Config flow for the Somfy RTS integration."""

from typing import Any

from rf_protocols import SomfyRTSButton, SomfyRTSCommand
import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import CONF_ADDRESS, CONF_TRANSMITTER, DOMAIN


def _parse_address(value: str) -> int | None:
    """Parse a hex string into a 24-bit Somfy RTS remote address.

    Returns None if the value is not a valid hex string or out of range.
    """
    try:
        address = int(value.strip(), 16)
    except ValueError:
        return None
    if not (0x1 <= address <= 0xFFFFFF):
        return None
    return address


class SomfyRTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Somfy RTS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        sample_command = SomfyRTSCommand(
            address=0x1, rolling_code=0, button=SomfyRTSButton.MY
        )
        try:
            transmitters = async_get_transmitters(
                self.hass, sample_command.frequency, sample_command.modulation
            )
        except HomeAssistantError:
            return self.async_abort(reason="no_transmitters")

        if not transmitters:
            return self.async_abort(reason="no_compatible_transmitters")

        errors: dict[str, str] = {}

        if user_input is not None:
            address = _parse_address(user_input[CONF_ADDRESS])
            if address is None:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                address_hex = format(address, "06X")
                await self.async_set_unique_id(address_hex)
                self._abort_if_unique_id_configured()

                registry = er.async_get(self.hass)
                entity_entry = registry.async_get(user_input[CONF_TRANSMITTER])
                assert entity_entry is not None

                return self.async_create_entry(
                    title=f"Somfy RTS {address_hex}",
                    data={
                        CONF_ADDRESS: address,
                        CONF_TRANSMITTER: entity_entry.id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): selector.TextSelector(),
                    vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                        selector.EntitySelectorConfig(include_entities=transmitters),
                    ),
                }
            ),
            errors=errors,
        )
