"""Support for LCN sensors."""
from __future__ import annotations

from typing import cast

import pypck

from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import LcnEntity
from .const import (
    CONF_DOMAIN_DATA,
    LED_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VARIABLES,
)
from .helpers import DeviceConnectionType, InputType, get_device_connection


def create_lcn_sensor_entity(
    hass: HomeAssistant, entity_config: ConfigType, config_entry: ConfigEntry
) -> LcnEntity:
    """Set up an entity for this domain."""
    device_connection = get_device_connection(
        hass, entity_config[CONF_ADDRESS], config_entry
    )

    if (
        entity_config[CONF_DOMAIN_DATA][CONF_SOURCE]
        in VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS
    ):
        return LcnVariableSensor(
            entity_config, config_entry.entry_id, device_connection
        )
    # in LED_PORTS + LOGICOP_PORTS
    return LcnLedLogicSensor(entity_config, config_entry.entry_id, device_connection)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    entities = []

    for entity_config in config_entry.data[CONF_ENTITIES]:
        if entity_config[CONF_DOMAIN] == DOMAIN_SENSOR:
            entities.append(create_lcn_sensor_entity(hass, entity_config, config_entry))

    async_add_entities(entities)


class LcnVariableSensor(LcnEntity, SensorEntity):
    """Representation of a LCN sensor for variables."""

    def __init__(
        self, config: ConfigType, entry_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN sensor."""
        super().__init__(config, entry_id, device_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_DOMAIN_DATA][CONF_UNIT_OF_MEASUREMENT]
        )

        self._value = None

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

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self._value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return cast(str, self.unit.value)

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.variable
        ):
            return

        self._value = input_obj.get_value().to_var_unit(self.unit)
        self.async_write_ha_state()


class LcnLedLogicSensor(LcnEntity, SensorEntity):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(
        self, config: ConfigType, entry_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize the LCN sensor."""
        super().__init__(config, entry_id, device_connection)

        if config[CONF_DOMAIN_DATA][CONF_SOURCE] in LED_PORTS:
            self.source = pypck.lcn_defs.LedPort[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        else:
            self.source = pypck.lcn_defs.LogicOpPort[
                config[CONF_DOMAIN_DATA][CONF_SOURCE]
            ]

        self._value = None

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

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self._value

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusLedsAndLogicOps):
            return

        if self.source in pypck.lcn_defs.LedPort:
            self._value = input_obj.get_led_state(self.source.value).name.lower()
        elif self.source in pypck.lcn_defs.LogicOpPort:
            self._value = input_obj.get_logic_op_state(self.source.value).name.lower()

        self.async_write_ha_state()
