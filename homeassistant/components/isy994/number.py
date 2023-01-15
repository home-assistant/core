"""Support for ISY number entities."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from pyisy.constants import ISY_VALUE_UNKNOWN, PROP_ON_LEVEL
from pyisy.helpers import EventListener, NodeProperty
from pyisy.variables import Variable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VARIABLES, PERCENTAGE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_VAR_SENSOR_STRING,
    DEFAULT_VAR_SENSOR_STRING,
    DOMAIN,
    UOM_8_BIT_RANGE,
)
from .entity import ISYAuxControlEntity
from .helpers import convert_isy_value_to_hass

ISY_MAX_SIZE = (2**32) / 2
ON_RANGE = (1, 255)  # Off is not included
CONTROL_DESC = {
    PROP_ON_LEVEL: NumberEntityDescription(
        key=PROP_ON_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1.0,
        native_max_value=100.0,
        native_step=1.0,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX number entities from config entry."""
    isy_data = hass.data[DOMAIN][config_entry.entry_id]
    device_info = isy_data.devices
    entities: list[ISYVariableNumberEntity | ISYAuxControlNumberEntity] = []
    var_id = config_entry.options.get(CONF_VAR_SENSOR_STRING, DEFAULT_VAR_SENSOR_STRING)

    for node in isy_data.variables[Platform.NUMBER]:
        step = 10 ** (-1 * int(node.prec))
        min_max = ISY_MAX_SIZE / (10 ** int(node.prec))
        description = NumberEntityDescription(
            key=node.address,
            name=node.name,
            entity_registry_enabled_default=var_id in node.name,
            native_unit_of_measurement=None,
            native_step=step,
            native_min_value=-min_max,
            native_max_value=min_max,
        )
        description_init = replace(
            description,
            key=f"{node.address}_init",
            name=f"{node.name} Initial Value",
            entity_category=EntityCategory.CONFIG,
        )

        entities.append(
            ISYVariableNumberEntity(
                node,
                unique_id=isy_data.uid_base(node),
                description=description,
                device_info=device_info[CONF_VARIABLES],
            )
        )
        entities.append(
            ISYVariableNumberEntity(
                node=node,
                unique_id=f"{isy_data.uid_base(node)}_init",
                description=description_init,
                device_info=device_info[CONF_VARIABLES],
                init_entity=True,
            )
        )

    for node, control in isy_data.aux_properties[Platform.NUMBER]:
        entities.append(
            ISYAuxControlNumberEntity(
                node=node,
                control=control,
                unique_id=f"{isy_data.uid_base(node)}_{control}",
                description=CONTROL_DESC[control],
                device_info=device_info.get(node.primary_node),
            )
        )
    async_add_entities(entities)


class ISYAuxControlNumberEntity(ISYAuxControlEntity, NumberEntity):
    """Representation of a ISY/IoX Aux Control Number entity."""

    _attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the variable."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]
        if node_prop.value == ISY_VALUE_UNKNOWN:
            return None

        if (
            self.entity_description.native_unit_of_measurement == PERCENTAGE
            and node_prop.uom == UOM_8_BIT_RANGE  # Insteon 0-255
        ):
            return ranged_value_to_percentage(ON_RANGE, node_prop.value)
        return int(node_prop.value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]

        if self.entity_description.native_unit_of_measurement == PERCENTAGE:
            value = (
                percentage_to_ranged_value(ON_RANGE, round(value))
                if node_prop.uom == UOM_8_BIT_RANGE
                else value
            )
        if self._control == PROP_ON_LEVEL:
            await self._node.set_on_level(value)
            return

        await self._node.send_cmd(self._control, val=value, uom=node_prop.uom)


class ISYVariableNumberEntity(NumberEntity):
    """Representation of an ISY variable as a number entity device."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _init_entity: bool
    _node: Variable
    entity_description: NumberEntityDescription

    def __init__(
        self,
        node: Variable,
        unique_id: str,
        description: NumberEntityDescription,
        device_info: DeviceInfo,
        init_entity: bool = False,
    ) -> None:
        """Initialize the ISY variable number."""
        self._node = node
        self.entity_description = description
        self._change_handler: EventListener | None = None

        # Two entities are created for each variable, one for current value and one for initial.
        # Initial value entities are disabled by default
        self._init_entity = init_entity
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status_events.subscribe(self.async_on_update)

    @callback
    def async_on_update(self, event: NodeProperty) -> None:
        """Handle the update event from the ISY Node."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the variable."""
        return convert_isy_value_to_hass(
            self._node.init if self._init_entity else self._node.status,
            "",
            self._node.prec,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get the state attributes for the device."""
        return {
            "last_edited": self._node.last_edited,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._node.set_value(value, init=self._init_entity)
