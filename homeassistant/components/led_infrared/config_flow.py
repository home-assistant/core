"""Config flow for the LED Infrared integration."""

import asyncio
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
    async_send_command,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from .entity import CODES

DEVICE_NAMES = {
    LEDIrDeviceType.GENERIC_10_KEY: "10-key remote",
    LEDIrDeviceType.GENERIC_10_KEY_B708: "10-key remote",
    LEDIrDeviceType.GENERIC_13_KEY: "13-key remote",
    LEDIrDeviceType.GENERIC_24_KEY: "24-key remote",
    LEDIrDeviceType.GENERIC_40_KEY: "40-key remote",
    LEDIrDeviceType.GENERIC_44_KEY: "44-key remote",
}

# Remotes that look identical but send different codes; the user picks the
# remote and the test step finds out which code set the device responds to.
DEVICE_VARIANTS = {
    LEDIrDeviceType.GENERIC_10_KEY: [
        LEDIrDeviceType.GENERIC_10_KEY,
        LEDIrDeviceType.GENERIC_10_KEY_B708,
    ],
}

SELECTABLE_DEVICE_TYPES = [
    device_type
    for device_type in LEDIrDeviceType
    if not any(device_type in variants[1:] for variants in DEVICE_VARIANTS.values())
]

_TOGGLE_GAP = 1.5


class LEDIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LED Infrared."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._user_input: dict[str, Any] = {}
        self._variants: list[LEDIrDeviceType] = []
        self._variant_index = 0

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
        if not emitter_entity_ids and not receiver_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            emitter_id = user_input.get(CONF_INFRARED_ENTITY_ID)
            receiver_id = user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
            if emitter_id or receiver_id:
                device_type = LEDIrDeviceType(user_input[CONF_DEVICE_TYPE])
                if emitter_id and device_type in DEVICE_VARIANTS:
                    self._user_input = user_input
                    self._variants = DEVICE_VARIANTS[device_type]
                    self._variant_index = 0
                    return await self.async_step_test_device()
                return self._async_create_led_entry(user_input)

            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                device_type.value
                                for device_type in SELECTABLE_DEVICE_TYPES
                            ],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=receiver_entity_ids,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/led_infrared"
            },
        )

    async def async_step_test_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Turn the light off, on and off again with the current code set."""
        codes = CODES[self._variants[self._variant_index]]
        emitter_id = self._user_input[CONF_INFRARED_ENTITY_ID]
        # Starting with off makes the correct code set visibly turn the light on
        # and off regardless of its initial state, while a wrong code set whose
        # off command is the right one's on leaves the light on.
        try:
            for code in (codes.OFF, codes.ON, codes.OFF):
                await async_send_command(self.hass, emitter_id, code.to_command())
                await asyncio.sleep(_TOGGLE_GAP)
        except HomeAssistantError:
            return await self.async_step_test_failed()
        return self.async_show_menu(
            step_id="test_device",
            menu_options=["finish", "next_variant"],
            description_placeholders=self._variant_placeholders(),
        )

    async def async_step_test_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the failure menu with only a retry option."""
        return self.async_show_menu(
            step_id="test_failed",
            menu_options=["test_device"],
            description_placeholders=self._variant_placeholders(),
        )

    def _variant_placeholders(self) -> dict[str, str]:
        """Return the placeholders describing the code set under test."""
        return {
            "variant": str(self._variant_index + 1),
            "variant_count": str(len(self._variants)),
        }

    async def async_step_next_variant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Test the next code set, starting over after the last one."""
        self._variant_index = (self._variant_index + 1) % len(self._variants)
        return await self.async_step_test_device()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry with the code set the device reacted to."""
        return self._async_create_led_entry(
            {
                **self._user_input,
                CONF_DEVICE_TYPE: self._variants[self._variant_index],
            }
        )

    def _async_create_led_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry unless the device is already configured."""
        emitter_id = data.get(CONF_INFRARED_ENTITY_ID)
        receiver_id = data.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
        if emitter_id:
            self._async_abort_entries_match(
                {
                    CONF_DEVICE_TYPE: data[CONF_DEVICE_TYPE],
                    CONF_INFRARED_ENTITY_ID: emitter_id,
                }
            )
        if receiver_id:
            self._async_abort_entries_match(
                {
                    CONF_DEVICE_TYPE: data[CONF_DEVICE_TYPE],
                    CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id,
                }
            )
        title_entity_id = emitter_id or receiver_id
        if TYPE_CHECKING:
            assert title_entity_id is not None
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(title_entity_id)
        title_entity_name = (
            entry.name or entry.original_name or title_entity_id
            if entry
            else title_entity_id
        )
        return self.async_create_entry(
            title=f"LED light with {DEVICE_NAMES[LEDIrDeviceType(data[CONF_DEVICE_TYPE])]} via {title_entity_name}",
            data=data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
        if not emitter_entity_ids and not receiver_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            emitter_id = user_input.get(CONF_INFRARED_ENTITY_ID)
            receiver_id = user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
            if emitter_id or receiver_id:
                if emitter_id:
                    self._async_abort_entries_match(
                        {
                            CONF_DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE],
                            CONF_INFRARED_ENTITY_ID: emitter_id,
                        }
                    )
                if receiver_id:
                    self._async_abort_entries_match(
                        {
                            CONF_DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE],
                            CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id,
                        }
                    )
                return self.async_update_reload_and_abort(
                    entry,
                    data={CONF_DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE], **user_input},
                )

            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=emitter_entity_ids,
                            )
                        ),
                        probatio.Optional(
                            CONF_INFRARED_RECEIVER_ENTITY_ID
                        ): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=receiver_entity_ids,
                            )
                        ),
                    }
                ),
                entry.data,
            ),
            errors=errors,
        )
