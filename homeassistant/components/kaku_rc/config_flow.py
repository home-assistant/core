"""Config flow for the Kaku RC 32 bit integration."""

from typing import Any

from rf_protocols.commands import ModulationType
from rf_protocols.commands.ook import OOKCommand
import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
    FREQUENCY_HZ,
)


_SAMPLE_COMMAND = OOKCommand(
    frequency=FREQUENCY_HZ,
    timings=[275],
    repeat_count=0,
)


def _resolve_transmitter_entity_id(
    hass, stored_value: str, available_transmitters: list[str]
) -> str:
    """Return a valid transmitter entity_id for selector defaults.

    Legacy config entries may store entity registry UUIDs instead of entity_id.
    """
    if stored_value in available_transmitters:
        return stored_value

    registry = er.async_get(hass)
    for entry in registry.entities.values():
        if entry.id == stored_value and entry.entity_id in available_transmitters:
            return entry.entity_id

    return available_transmitters[0]


class KakuRcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kaku RC 32 bit."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this config entry."""
        return KakuRcOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the single-step add flow."""
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
            return self.async_create_entry(
                title=f"Kaku ID {device_id} CH {channel}",
                data={
                    CONF_TRANSMITTER: transmitter,
                    CONF_DEVICE_ID: device_id,
                    CONF_CHANNEL: channel,
                    CONF_GROUP: group,
                    CONF_DIM: dim,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_user_schema(transmitters),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        config_entry = self._get_reconfigure_entry()

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

        defaults = {
            CONF_TRANSMITTER: _resolve_transmitter_entity_id(
                self.hass,
                str(config_entry.data.get(CONF_TRANSMITTER, "")),
                transmitters,
            ),
            CONF_DEVICE_ID: config_entry.data.get(CONF_DEVICE_ID, 123456),
            CONF_CHANNEL: config_entry.data.get(CONF_CHANNEL, 1),
            CONF_GROUP: config_entry.data.get(CONF_GROUP, False),
            CONF_DIM: config_entry.data.get(CONF_DIM, False),
        }

        if user_input is not None:
            transmitter: str = user_input[CONF_TRANSMITTER]
            device_id: int = user_input[CONF_DEVICE_ID]
            channel: int = user_input[CONF_CHANNEL]
            group: bool = user_input[CONF_GROUP]
            dim: bool = user_input[CONF_DIM]

            if not (0 <= device_id <= 0x3FFFFFF):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._async_user_schema(transmitters, user_input),
                    errors={CONF_DEVICE_ID: "invalid_device_id"},
                )
            if not (1 <= channel <= 16):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._async_user_schema(transmitters, user_input),
                    errors={CONF_CHANNEL: "invalid_channel"},
                )

            return self.async_update_reload_and_abort(
                config_entry,
                data_updates={
                    CONF_TRANSMITTER: transmitter,
                    CONF_DEVICE_ID: device_id,
                    CONF_CHANNEL: channel,
                    CONF_GROUP: group,
                    CONF_DIM: dim,
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._async_user_schema(transmitters, defaults),
        )

    def _async_user_schema(
        self,
        transmitters: list[str],
        user_input: dict[str, Any] | None = None,
    ) -> vol.Schema:
        """Build the one-step add form schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_TRANSMITTER,
                    default=(user_input or {}).get(CONF_TRANSMITTER, transmitters[0]),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(include_entities=transmitters),
                ),
                vol.Required(
                    CONF_DEVICE_ID,
                    default=(user_input or {}).get(CONF_DEVICE_ID, 123456),
                ): vol.All(
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
                    default=(user_input or {}).get(CONF_CHANNEL, 1),
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
                    default=(user_input or {}).get(CONF_GROUP, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_DIM,
                    default=(user_input or {}).get(CONF_DIM, False),
                ): selector.BooleanSelector(),
            }
        )


class KakuRcOptionsFlow(OptionsFlow):
    """Handle options flow for Kaku RC 32 bit."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow (reconfigure)."""
        config_entry = self.config_entry

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

        current_transmitter = _resolve_transmitter_entity_id(
            self.hass,
            str(config_entry.data.get(CONF_TRANSMITTER, "")),
            transmitters,
        )

        errors: dict[str, str] = {}

        if user_input is not None:
            device_id: int = user_input[CONF_DEVICE_ID]
            channel: int = user_input[CONF_CHANNEL]
            group: bool = user_input[CONF_GROUP]
            transmitter: str = user_input[CONF_TRANSMITTER]
            dim: bool = user_input[CONF_DIM]

            if not (0 <= device_id <= 0x3FFFFFF):
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            elif not (1 <= channel <= 16):
                errors[CONF_CHANNEL] = "invalid_channel"
            else:
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data={
                        CONF_TRANSMITTER: transmitter,
                        CONF_DEVICE_ID: device_id,
                        CONF_CHANNEL: channel,
                        CONF_GROUP: group,
                        CONF_DIM: dim,
                    },
                )
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRANSMITTER,
                    default=current_transmitter,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(include_entities=transmitters),
                ),
                vol.Required(
                    CONF_DEVICE_ID,
                    default=config_entry.data.get(CONF_DEVICE_ID, 123456),
                ): vol.All(
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
                    default=config_entry.data.get(CONF_CHANNEL, 1),
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
                    default=config_entry.data.get(CONF_GROUP, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_DIM,
                    default=config_entry.data.get(CONF_DIM, False),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
