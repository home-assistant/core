"""Config flow for Dyson Infrared integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components import infrared
from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TEMPERATURE_UNIT, UnitOfTemperature
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_COMMAND_STEP_DELAY,
    DOMAIN,
    DysonDeviceType,
    DysonTemperatureUnit,
)

DEVICE_TYPE_NAMES: dict[DysonDeviceType, str] = {
    DysonDeviceType.FAN: "Fan",
    DysonDeviceType.HEATER_COOLER: "Heater/Cooler",
}


class DysonIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson Infrared."""

    VERSION = 1

    _data: dict[str, Any]
    _title: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where the user configures the integration."""

        emitter_entity_ids = infrared.async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
            device_type = DysonDeviceType(user_input[CONF_DEVICE_TYPE])

            await self.async_set_unique_id(f"{device_type.value}_{entity_id}")
            self._abort_if_unique_id_configured()

            ent_reg = er.async_get(self.hass)
            entry = ent_reg.async_get(entity_id)
            entity_name = (
                entry.name or entry.original_name or entity_id if entry else entity_id
            )
            device_type_name = DEVICE_TYPE_NAMES[device_type]

            self._data = user_input
            self._title = f"Dyson {device_type_name} via {entity_name}"

            if device_type is DysonDeviceType.HEATER_COOLER:
                return await self.async_step_heater_cooler()

            return self.async_create_entry(title=self._title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                device_type.value for device_type in DysonDeviceType
                            ],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    vol.Optional(
                        CONF_COMMAND_STEP_DELAY, default=DEFAULT_COMMAND_STEP_DELAY
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=5,
                            step=0.05,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_heater_cooler(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the settings that only apply to a heater/cooler."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._title, data={**self._data, **user_input}
            )

        default_temperature_unit = (
            DysonTemperatureUnit.FAHRENHEIT
            if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT
            else DysonTemperatureUnit.CELSIUS
        ).value

        return self.async_show_form(
            step_id="heater_cooler",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TEMPERATURE_UNIT, default=default_temperature_unit
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[unit.value for unit in DysonTemperatureUnit],
                            translation_key=CONF_TEMPERATURE_UNIT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
