"""Config flow for NAD Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DEVICE_NAMES,
    DOMAIN,
    NADDeviceType,
)


class NadIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for NAD Infrared."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device type selection."""
        if not async_get_emitters(self.hass):
            return self.async_abort(reason="no_infrared_emitters")

        return self.async_show_menu(
            step_id="user",
            menu_options=[device_type.value for device_type in NADDeviceType],
        )

    async def async_step_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle receiver emitter selection."""
        return await self._async_step_device(NADDeviceType.RECEIVER, user_input)

    async def async_step_amplifier(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle amplifier emitter selection."""
        return await self._async_step_device(NADDeviceType.AMPLIFIER, user_input)

    async def async_step_cd_player(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle CD player emitter selection."""
        return await self._async_step_device(NADDeviceType.CD_PLAYER, user_input)

    async def async_step_cassette_deck(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle cassette deck emitter selection."""
        return await self._async_step_device(NADDeviceType.CASSETTE_DECK, user_input)

    async def _async_step_device(
        self, device_type: NADDeviceType, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Select the emitter for a device type and create the entry."""
        if user_input is not None:
            data = {CONF_DEVICE_TYPE: device_type, **user_input}
            self._async_abort_entries_match(data)
            return self.async_create_entry(title=DEVICE_NAMES[device_type], data=data)

        return self.async_show_form(
            step_id=device_type.value,
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=async_get_emitters(self.hass),
                        )
                    ),
                }
            ),
        )
