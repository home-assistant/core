"""Config flow for the Somfy RTS integration."""

from typing import Any

from rf_protocols.codes.somfy.rts import SomfyRTSButton
from rf_protocols.commands.somfy_rts import SomfyRTSCommand
import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters, async_send_command
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import CONF_ADDRESS, CONF_ROLLING_CODE, CONF_TRANSMITTER, DOMAIN


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

    def __init__(self) -> None:
        """Initialize config flow."""
        self._address: int | None = None
        self._transmitter_id: str | None = None
        self._rolling_code: int = 0

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
                self._address = address
                self._transmitter_id = entity_entry.id
                return await self.async_step_prog()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): selector.TextSelector(),
                        vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                            selector.EntitySelectorConfig(include_entities=transmitters),
                        ),
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_prog(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the PROG pairing step."""
        assert self._address is not None
        assert self._transmitter_id is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("send_prog"):
                self._rolling_code += 1
                command = SomfyRTSCommand(
                    address=self._address,
                    rolling_code=self._rolling_code,
                    button=SomfyRTSButton.PROG,
                    frame_repeats=4,
                )
                try:
                    await async_send_command(self.hass, self._transmitter_id, command)
                except HomeAssistantError:
                    errors["base"] = "prog_failed"
                    self._rolling_code -= 1
            else:
                address_hex = format(self._address, "06X")
                return self.async_create_entry(
                    title=f"Somfy RTS {address_hex}",
                    data={
                        CONF_ADDRESS: self._address,
                        CONF_TRANSMITTER: self._transmitter_id,
                        CONF_ROLLING_CODE: self._rolling_code,
                    },
                )

        return self.async_show_form(
            step_id="prog",
            data_schema=vol.Schema(
                {
                    vol.Optional("send_prog", default=False): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )
