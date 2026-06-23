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

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self._device_type: LGDeviceType | None = None

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
        receiver_entity_ids = async_get_receivers(self.hass)
        if not emitter_entity_ids and not receiver_entity_ids:
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
                            options=[device_type.value for device_type in LGDeviceType],
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
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
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
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=receiver_entity_ids,
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
        emitter_entity_ids = async_get_emitters(self.hass)
        receiver_entity_ids = async_get_receivers(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            return await self._async_create_device_entry(LGDeviceType.AC, user_input)

        return self.async_show_form(
            step_id="ac",
            data_schema=self._ac_schema(emitter_entity_ids, receiver_entity_ids),
            errors=errors,
        )

    def _ac_schema(
        self,
        emitter_entity_ids: list[str],
        receiver_entity_ids: list[str],
    ) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=emitter_entity_ids,
                    )
                ),
                vol.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=receiver_entity_ids,
                    )
                ),
                vol.Required(
                    CONF_HVAC_MODES,
                    default=_DEFAULT_HVAC_MODES,
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
