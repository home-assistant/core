"""Support for LCN binary sensors."""

from collections.abc import Iterable
from functools import partial

import pypck

from homeassistant.components.binary_sensor import (
    DOMAIN as DOMAIN_BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DOMAIN_DATA
from .entity import LcnEntity
from .helpers import InputType, LcnConfigEntry

PARALLEL_UPDATES = 0


def add_lcn_entities(
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities = [
        LcnBinarySensor(entity_config, config_entry) for entity_config in entity_configs
    ]
    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    config_entry.runtime_data.add_entities_callbacks.update(
        {DOMAIN_BINARY_SENSOR: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_BINARY_SENSOR
        ),
    )


class LcnBinarySensor(LcnEntity, BinarySensorEntity):
    """Representation of a LCN binary sensor for binary sensor ports."""

    def __init__(self, config: ConfigType, config_entry: LcnConfigEntry) -> None:
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
