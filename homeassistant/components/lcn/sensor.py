"""Support for LCN sensors."""

from collections.abc import Iterable
from functools import partial
from itertools import chain
from typing import cast

import pypck

from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    DOMAIN,
    LED_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VARIABLES,
)
from .entity import LcnEntity
from .helpers import InputType


def add_lcn_entities(
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities: list[LcnVariableSensor | LcnLedLogicSensor] = []
    for entity_config in entity_configs:
        if entity_config[CONF_DOMAIN_DATA][CONF_SOURCE] in chain(
            VARIABLES, SETPOINTS, THRESHOLDS, S0_INPUTS
        ):
            entities.append(LcnVariableSensor(entity_config, config_entry))
        else:  # in LED_PORTS + LOGICOP_PORTS
            entities.append(LcnLedLogicSensor(entity_config, config_entry))

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    hass.data[DOMAIN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS].update(
        {DOMAIN_SENSOR: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_SENSOR
        ),
    )


class LcnVariableSensor(LcnEntity, SensorEntity):
    """Representation of a LCN sensor for variables."""

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN sensor."""
        super().__init__(config, config_entry)

        self.variable = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_DOMAIN_DATA][CONF_UNIT_OF_MEASUREMENT]
        )
        self._attr_native_unit_of_measurement = cast(str, self.unit.value)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.variable)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.variable)

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.variable
        ):
            return

        self._attr_native_value = input_obj.get_value().to_var_unit(self.unit)
        self.async_write_ha_state()


class LcnLedLogicSensor(LcnEntity, SensorEntity):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN sensor."""
        super().__init__(config, config_entry)

        if config[CONF_DOMAIN_DATA][CONF_SOURCE] in LED_PORTS:
            self.source = pypck.lcn_defs.LedPort[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        else:
            self.source = pypck.lcn_defs.LogicOpPort[
                config[CONF_DOMAIN_DATA][CONF_SOURCE]
            ]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.source)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.source)

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusLedsAndLogicOps):
            return

        if self.source in pypck.lcn_defs.LedPort:
            self._attr_native_value = input_obj.get_led_state(
                self.source.value
            ).name.lower()
        elif self.source in pypck.lcn_defs.LogicOpPort:
            self._attr_native_value = input_obj.get_logic_op_state(
                self.source.value
            ).name.lower()

        self.async_write_ha_state()
