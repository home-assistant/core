"""Config flow for LG IR integration."""

from typing import TYPE_CHECKING, Any, override

import probatio

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
) -> probatio.Schema:
    """Return the emitter/receiver selection schema shared by every device type."""
    emitter_marker = probatio.Required if emitter_required else probatio.Optional
    return probatio.Schema(
        {
            emitter_marker(CONF_INFRARED_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_emitters(hass),
                )
            ),
            probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_receivers(hass),
                )
            ),
        }
    )


@callback
def _ac_schema(hass: HomeAssistant) -> probatio.Schema:
    """Return the AC schema: emitter, optional receiver and supported modes."""
    return _infrared_entity_schema(hass, emitter_required=True).extend(
        {
            probatio.Required(
                CONF_HVAC_MODES, default=_DEFAULT_HVAC_MODES
            ): probatio.All(
                SelectSelector(
                    SelectSelectorConfig(
                        options=[mode.value for mode in _HVAC_MODE_OPTIONS],
                        translation_key=CONF_HVAC_MODES,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
                probatio.Length(min=1, msg="no_hvac_modes"),
            )
        }
    )


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 2

    def _entity_name(self, entity_id: str) -> str:
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        return entry.name or entry.original_name or entity_id if entry else entity_id

    @callback
    def _async_abort_infrared_entities_match(
        self, device_type: LGDeviceType, user_input: dict[str, Any]
    ) -> None:
        """Abort if another entry of this device type uses one of these IR entities."""
        if emitter_id := user_input.get(CONF_INFRARED_ENTITY_ID):
            self._async_abort_entries_match(
                {CONF_DEVICE_TYPE: device_type, CONF_INFRARED_ENTITY_ID: emitter_id}
            )
        if receiver_id := user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
            self._async_abort_entries_match(
                {
                    CONF_DEVICE_TYPE: device_type,
                    CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id,
                }
            )

    async def _async_create_device_entry(
        self, device_type: LGDeviceType, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Abort on a duplicate IR entity and create the entry for the device."""
        self._async_abort_infrared_entities_match(device_type, user_input)

        title_entity_id = user_input.get(CONF_INFRARED_ENTITY_ID) or user_input.get(
            CONF_INFRARED_RECEIVER_ENTITY_ID
        )
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

        return self.async_show_form(step_id="ac", data_schema=_ac_schema(self.hass))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the infrared entities and supported modes."""
        entry = self._get_reconfigure_entry()
        device_type = LGDeviceType(entry.data[CONF_DEVICE_TYPE])
        errors: dict[str, str] = {}

        if device_type is LGDeviceType.AC:
            if not async_get_emitters(self.hass):
                return self.async_abort(reason="no_infrared_emitters")
            data_schema = _ac_schema(self.hass)
        else:
            if not async_get_emitters(self.hass) and not async_get_receivers(self.hass):
                return self.async_abort(reason="no_infrared_entities")
            data_schema = _infrared_entity_schema(self.hass, emitter_required=False)

        if user_input is not None:
            if device_type is LGDeviceType.TV and not (
                user_input.get(CONF_INFRARED_ENTITY_ID)
                or user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID)
            ):
                errors["base"] = "missing_infrared_entity"
            else:
                self._async_abort_infrared_entities_match(device_type, user_input)
                # Replace rather than update the data, so a cleared optional
                # selector removes that entity from the entry.
                return self.async_update_reload_and_abort(
                    entry, data={CONF_DEVICE_TYPE: device_type, **user_input}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(data_schema, entry.data),
            errors=errors,
        )
