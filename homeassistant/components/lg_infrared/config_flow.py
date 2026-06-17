"""Config flow for LG IR integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
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


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._device_type: LGDeviceType | None = None

    def _entity_name(self, entity_id: str) -> str:
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        return entry.name or entry.original_name or entity_id if entry else entity_id

    async def _async_create_device_entry(
        self,
        device_type: LGDeviceType,
        entity_id: str,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Set the unique ID and create the entry for the selected device."""
        await self.async_set_unique_id(f"lg_ir_{device_type}_{entity_id}")
        self._abort_if_unique_id_configured()

        name = self._entity_name(entity_id)
        return self.async_create_entry(
            title=f"LG {DEVICE_TYPE_NAMES[device_type]} via {name}",
            data={CONF_DEVICE_TYPE: device_type, **user_input},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device type selection."""
        emitter_ids = async_get_emitters(self.hass)
        receiver_ids = async_get_receivers(self.hass)
        if not emitter_ids and not receiver_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            self._device_type = LGDeviceType(user_input[CONF_DEVICE_TYPE])
            if self._device_type == LGDeviceType.TV:
                return await self.async_step_tv()
            return await self.async_step_ac()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[dt.value for dt in LGDeviceType],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle TV entity selection."""
        emitter_ids = async_get_emitters(self.hass)
        receiver_ids = async_get_receivers(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            if entity_id := user_input.get(CONF_INFRARED_ENTITY_ID) or user_input.get(
                CONF_INFRARED_RECEIVER_ENTITY_ID
            ):
                return await self._async_create_device_entry(
                    LGDeviceType.TV, entity_id, user_input
                )
            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="tv",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_ids,
                        )
                    ),
                    vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=receiver_ids,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_ac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle AC entity and mode selection."""
        emitter_ids = async_get_emitters(self.hass)
        receiver_ids = async_get_receivers(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            if emitter_id := user_input.get(CONF_INFRARED_ENTITY_ID):
                return await self._async_create_device_entry(
                    LGDeviceType.AC, emitter_id, user_input
                )
            errors[CONF_INFRARED_ENTITY_ID] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="ac",
            data_schema=self._ac_schema(emitter_ids, receiver_ids),
            errors=errors,
        )

    def _ac_schema(
        self,
        emitter_ids: list[str],
        receiver_ids: list[str],
        default_emitter: str | None = None,
        default_receiver: str | None = None,
        default_modes: list[str] | None = None,
    ) -> vol.Schema:
        emitter_kwargs: dict[str, Any] = {}
        if default_emitter:
            emitter_kwargs["default"] = default_emitter

        receiver_kwargs: dict[str, Any] = {}
        if default_receiver:
            receiver_kwargs["default"] = default_receiver

        return vol.Schema(
            {
                vol.Required(CONF_INFRARED_ENTITY_ID, **emitter_kwargs): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=emitter_ids,
                    )
                ),
                vol.Optional(
                    CONF_INFRARED_RECEIVER_ENTITY_ID, **receiver_kwargs
                ): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=receiver_ids,
                    )
                ),
                vol.Required(
                    CONF_HVAC_MODES,
                    default=default_modes
                    if default_modes is not None
                    else _DEFAULT_HVAC_MODES,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[m.value for m in _HVAC_MODE_OPTIONS],
                        translation_key=CONF_HVAC_MODES,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
            }
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry: ConfigEntry = self._get_reconfigure_entry()
        device_type = LGDeviceType(entry.data[CONF_DEVICE_TYPE])
        emitter_ids = async_get_emitters(self.hass)
        receiver_ids = async_get_receivers(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            if device_type == LGDeviceType.TV:
                if user_input.get(CONF_INFRARED_ENTITY_ID) or user_input.get(
                    CONF_INFRARED_RECEIVER_ENTITY_ID
                ):
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )
                errors["base"] = "missing_infrared_entity"
            else:
                if user_input.get(CONF_INFRARED_ENTITY_ID):
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )
                errors[CONF_INFRARED_ENTITY_ID] = "missing_infrared_entity"

        if device_type == LGDeviceType.TV:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_INFRARED_ENTITY_ID,
                        default=entry.data.get(CONF_INFRARED_ENTITY_ID, vol.UNDEFINED),
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_ids,
                        )
                    ),
                    vol.Optional(
                        CONF_INFRARED_RECEIVER_ENTITY_ID,
                        default=entry.data.get(
                            CONF_INFRARED_RECEIVER_ENTITY_ID, vol.UNDEFINED
                        ),
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=receiver_ids,
                        )
                    ),
                }
            )
        else:
            schema = self._ac_schema(
                emitter_ids,
                receiver_ids,
                default_emitter=entry.data.get(CONF_INFRARED_ENTITY_ID),
                default_receiver=entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID),
                default_modes=entry.data.get(CONF_HVAC_MODES, _DEFAULT_HVAC_MODES),
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )
