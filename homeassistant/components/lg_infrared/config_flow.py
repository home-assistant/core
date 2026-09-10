"""Config flow for LG IR integration."""

from typing import TYPE_CHECKING, Any, override

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
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
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)

DEVICE_TYPE_NAMES: dict[LGDeviceType, str] = {
    LGDeviceType.TV: "TV",
    LGDeviceType.AC: "AC",
}

_HVAC_MODE_OPTIONS = [
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]
_DEFAULT_HVAC_MODES = [HVACMode.COOL, HVACMode.DRY]


@callback
def _infrared_entity_schema(
    hass: HomeAssistant, *, emitter_required: bool
) -> vol.Schema:
    """Return the emitter/receiver selection schema shared by every device type."""
    emitter_marker = vol.Required if emitter_required else vol.Optional
    return vol.Schema(
        {
            emitter_marker(CONF_INFRARED_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_emitters(hass),
                )
            ),
            vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_receivers(hass),
                )
            ),
        }
    )


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 2

    def _entity_name(self, entity_id: str) -> str:
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        return entry.name or entry.original_name or entity_id if entry else entity_id

    async def _async_create_device_entry(
        self, device_type: LGDeviceType, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Abort on a duplicate IR entity and create the entry for the device."""
        emitter_id = user_input.get(CONF_INFRARED_ENTITY_ID)
        receiver_id = user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
        if emitter_id:
            self._async_abort_entries_match(
                {CONF_DEVICE_TYPE: device_type, CONF_INFRARED_ENTITY_ID: emitter_id}
            )
        if receiver_id:
            self._async_abort_entries_match(
                {
                    CONF_DEVICE_TYPE: device_type,
                    CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id,
                }
            )

        title_entity_id = emitter_id or receiver_id
        if TYPE_CHECKING:
            assert title_entity_id is not None
        return self.async_create_entry(
            title=f"LG {DEVICE_TYPE_NAMES[device_type]} via "
            f"{self._entity_name(title_entity_id)}",
            data={CONF_DEVICE_TYPE: device_type, **user_input},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device type selection."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids and not async_get_receivers(self.hass):
            return self.async_abort(reason="no_infrared_entities")

        menu_options = [LGDeviceType.TV.value]
        # The AC step requires an emitter, so offering it without one dead-ends.
        if emitter_entity_ids:
            menu_options.append(LGDeviceType.AC.value)

        return self.async_show_menu(step_id="user", menu_options=menu_options)

    async def async_step_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle TV entity selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_INFRARED_ENTITY_ID) or user_input.get(
                CONF_INFRARED_RECEIVER_ENTITY_ID
            ):
                return await self._async_create_device_entry(
                    LGDeviceType.TV, user_input
                )
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="tv",
            data_schema=_infrared_entity_schema(self.hass, emitter_required=False),
            errors=errors,
        )

    async def async_step_ac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle AC entity and mode selection."""
        if user_input is not None:
            return await self._async_create_device_entry(LGDeviceType.AC, user_input)

        return self.async_show_form(
            step_id="ac",
            data_schema=_infrared_entity_schema(
                self.hass, emitter_required=True
            ).extend(
                {
                    vol.Required(CONF_HVAC_MODES, default=_DEFAULT_HVAC_MODES): vol.All(
                        SelectSelector(
                            SelectSelectorConfig(
                                options=[mode.value for mode in _HVAC_MODE_OPTIONS],
                                translation_key=CONF_HVAC_MODES,
                                mode=SelectSelectorMode.LIST,
                                multiple=True,
                            )
                        ),
                        vol.Length(min=1, msg="no_hvac_modes"),
                    )
                }
            ),
        )
