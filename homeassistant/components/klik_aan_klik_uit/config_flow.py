"""Config flow for the KlikAanKlikUit RC integration."""

from typing import Any

from rf_protocols.commands import ModulationType
import voluptuous as vol

from homeassistant.components.radio_frequency import (
    async_get_transmitters,
    async_send_command,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
    REPEAT_COUNT_LEARN,
)
from rf_protocols.commands.kaku import KakuCommand

_SAMPLE_COMMAND = KakuCommand(
    id=0,
    channel=1,
    group=False,
    on=True,
)
_CONF_DEVICE_RESPONDED = "device_responded"


class KakuRcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KlikAanKlikUit."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._device_data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle collecting initial setup data."""
        try:
            transmitters = async_get_transmitters(
                self.hass,
                _SAMPLE_COMMAND.frequency,
                ModulationType.OOK,
            )
        except HomeAssistantError:
            return self.async_abort(reason="no_transmitters")

        if not transmitters:
            return self.async_abort(reason="no_compatible_transmitters")

        if user_input is not None:
            transmitter: str = user_input[CONF_TRANSMITTER]
            device_id: int = user_input[CONF_DEVICE_ID]
            channel: int = user_input[CONF_CHANNEL]
            group: bool = user_input[CONF_GROUP]
            dim: bool = user_input[CONF_DIM]

            if not (0 <= device_id <= 0x3FFFFFF):
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._async_user_schema(transmitters, user_input),
                    errors={CONF_DEVICE_ID: "invalid_device_id"},
                )
            if not (1 <= channel <= 16):
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._async_user_schema(transmitters, user_input),
                    errors={CONF_CHANNEL: "invalid_channel"},
                )

            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(transmitter)
            assert entity_entry is not None
            await self.async_set_unique_id(
                f"{entity_entry.id}_{device_id}_{channel}_{int(group)}"
            )
            self._abort_if_unique_id_configured()
            self._device_data = {
                CONF_TRANSMITTER: transmitter,
                CONF_DEVICE_ID: device_id,
                CONF_CHANNEL: channel,
                CONF_GROUP: group,
                CONF_DIM: dim,
            }
            return await self.async_step_pairing_mode()

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_user_schema(transmitters),
        )

    async def async_step_pairing_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user to put the target device in pairing mode."""
        if user_input is None:
            return self.async_show_form(
                step_id="pairing_mode",
                data_schema=vol.Schema({}),
            )

        assert self._device_data is not None
        command = KakuCommand(
            id=self._device_data[CONF_DEVICE_ID],
            channel=self._device_data[CONF_CHANNEL],
            group=self._device_data[CONF_GROUP],
            on=True,
            frame_repeats=REPEAT_COUNT_LEARN,
        )
        await async_send_command(
            self.hass,
            self._device_data[CONF_TRANSMITTER],
            command,
        )
        return await self.async_step_pairing_result()

    async def async_step_pairing_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm whether the device responded to the learn command."""
        if user_input is not None:
            if user_input[_CONF_DEVICE_RESPONDED]:
                assert self._device_data is not None
                title = (
                    f"KlikAanKlikUit ID {self._device_data[CONF_DEVICE_ID]} "
                    f"CH {self._device_data[CONF_CHANNEL]}"
                )
                return self.async_create_entry(
                    title=title,
                    data=self._device_data,
                )

            return self.async_show_form(
                step_id="pairing_mode",
                data_schema=vol.Schema({}),
                errors={"base": "no_response"},
            )

        return self.async_show_form(
            step_id="pairing_result",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        _CONF_DEVICE_RESPONDED,
                        default=False,
                    ): selector.BooleanSelector()
                }
            ),
        )

    def _async_user_schema(
        self,
        transmitters: list[str],
        user_input: dict[str, Any] | None = None,
    ) -> vol.Schema:
        """Build the one-step add form schema."""
        if user_input is None:
            user_input = {}

        device_id_key = (
            vol.Required(CONF_DEVICE_ID, default=user_input[CONF_DEVICE_ID])
            if CONF_DEVICE_ID in user_input
            else vol.Required(CONF_DEVICE_ID)
        )

        return vol.Schema(
            {
                vol.Required(
                    CONF_TRANSMITTER,
                    default=user_input.get(CONF_TRANSMITTER, transmitters[0]),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(include_entities=transmitters),
                ),
                device_id_key: vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=0x3FFFFFF,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_CHANNEL,
                    default=user_input.get(CONF_CHANNEL, 1),
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=16,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_GROUP,
                    default=user_input.get(CONF_GROUP, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_DIM,
                    default=user_input.get(CONF_DIM, False),
                ): selector.BooleanSelector(),
            }
        )
