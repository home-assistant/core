"""Support for LCN binary sensors."""

from collections.abc import Iterable
from functools import partial

import pypck

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.binary_sensor import (
    DOMAIN as DOMAIN_BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    BINSENSOR_PORTS,
    CONF_DOMAIN_DATA,
    DOMAIN,
    SETPOINTS,
)
from .entity import LcnEntity
from .helpers import InputType


def add_lcn_entities(
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities: list[LcnRegulatorLockSensor | LcnBinarySensor | LcnLockKeysSensor] = []
    for entity_config in entity_configs:
        if entity_config[CONF_DOMAIN_DATA][CONF_SOURCE] in SETPOINTS:
            entities.append(LcnRegulatorLockSensor(entity_config, config_entry))
        elif entity_config[CONF_DOMAIN_DATA][CONF_SOURCE] in BINSENSOR_PORTS:
            entities.append(LcnBinarySensor(entity_config, config_entry))
        else:  # in KEY
            entities.append(LcnLockKeysSensor(entity_config, config_entry))

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
        {DOMAIN_BINARY_SENSOR: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_BINARY_SENSOR
        ),
    )


class LcnRegulatorLockSensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN binary sensor for regulator locks."""

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN binary sensor."""
        super().__init__(config, config_entry)

        self.setpoint_variable = pypck.lcn_defs.Var[
            config[CONF_DOMAIN_DATA][CONF_SOURCE]
        ]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(
                self.setpoint_variable
            )

        entity_automations = automations_with_entity(self.hass, self.entity_id)
        entity_scripts = scripts_with_entity(self.hass, self.entity_id)
        if entity_automations + entity_scripts:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_binary_sensor_{self.entity_id}",
                breaks_in_ha_version="2025.5.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_regulatorlock_sensor",
                translation_placeholders={
                    "entity": f"{DOMAIN_BINARY_SENSOR}.{self.name.lower().replace(' ', '_')}",
                },
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(
                self.setpoint_variable
            )

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.setpoint_variable
        ):
            return

        self._attr_is_on = input_obj.get_value().is_locked_regulator()
        self.async_write_ha_state()


class LcnBinarySensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN binary sensor for binary sensor ports."""

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN binary sensor."""
        super().__init__(config, config_entry)

        self.bin_sensor_port = pypck.lcn_defs.BinSensorPort[
            config[CONF_DOMAIN_DATA][CONF_SOURCE]
        ]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(
                self.bin_sensor_port
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(
                self.bin_sensor_port
            )

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusBinSensors):
            return

        self._attr_is_on = input_obj.get_state(self.bin_sensor_port.value)
        self.async_write_ha_state()


class LcnLockKeysSensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN sensor for key locks."""

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN sensor."""
        super().__init__(config, config_entry)

        self.source = pypck.lcn_defs.Key[config[CONF_DOMAIN_DATA][CONF_SOURCE]]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.source)

        entity_automations = automations_with_entity(self.hass, self.entity_id)
        entity_scripts = scripts_with_entity(self.hass, self.entity_id)
        if entity_automations + entity_scripts:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_binary_sensor_{self.entity_id}",
                breaks_in_ha_version="2025.5.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_keylock_sensor",
                translation_placeholders={
                    "entity": f"{DOMAIN_BINARY_SENSOR}.{self.name.lower().replace(' ', '_')}",
                },
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.source)

    def input_received(self, input_obj: InputType) -> None:
        """Set sensor value when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusKeyLocks)
            or self.source not in pypck.lcn_defs.Key
        ):
            return

        table_id = ord(self.source.name[0]) - 65
        key_id = int(self.source.name[1]) - 1

        self._attr_is_on = input_obj.get_state(table_id, key_id)
        self.async_write_ha_state()
