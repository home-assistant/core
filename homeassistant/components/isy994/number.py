"""Support for ISY number entities."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pyisy.constants import (
    ATTR_ACTION,
    CMD_BACKLIGHT,
    DEV_BL_ADDR,
    DEV_CMD_MEMORY_WRITE,
    DEV_MEMORY,
    ISY_VALUE_UNKNOWN,
    PROP_ON_LEVEL,
    TAG_ADDRESS,
    UOM_PERCENTAGE,
)
from pyisy.helpers import EventListener, NodeProperty
from pyisy.nodes import Node, NodeChangedEvent
from pyisy.variables import Variable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_VARIABLES,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
from .models import IsyData

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
    ),
    CMD_BACKLIGHT: NumberEntityDescription(
        key=CMD_BACKLIGHT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
}
BACKLIGHT_MEMORY_FILTER = {"memory": DEV_BL_ADDR, "cmd1": DEV_CMD_MEMORY_WRITE}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISY/IoX number entities from config entry."""
    isy_data: IsyData = hass.data[DOMAIN][config_entry.entry_id]
    device_info = isy_data.devices
    entities: list[
        ISYVariableNumberEntity | ISYAuxControlNumberEntity | ISYBacklightNumberEntity
    ] = []
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
        entity_init_info = {
            "node": node,
            "control": control,
            "unique_id": f"{isy_data.uid_base(node)}_{control}",
            "description": CONTROL_DESC[control],
            "device_info": device_info.get(node.primary_node),
        }
        if control == CMD_BACKLIGHT:
            entities.append(ISYBacklightNumberEntity(**entity_init_info))
            continue
        entities.append(ISYAuxControlNumberEntity(**entity_init_info))
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

        if not await self._node.send_cmd(self._control, val=value, uom=node_prop.uom):
            raise HomeAssistantError(
                f"Could not set {self.name} to {value} for {self._node.address}"
            )


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
        if not await self._node.set_value(value, init=self._init_entity):
            raise HomeAssistantError(
                f"Could not set {self.name} to {value} for {self._node.address}"
            )


class ISYBacklightNumberEntity(ISYAuxControlEntity, RestoreNumber):
    """Representation of a ISY/IoX Backlight Number entity."""

    _assumed_state = True  # Backlight values aren't read from device

    def __init__(
        self,
        node: Node,
        control: str,
        unique_id: str,
        description: NumberEntityDescription,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the ISY Backlight number entity."""
        super().__init__(node, control, unique_id, description, device_info)
        self._memory_change_handler: EventListener | None = None
        self._attr_native_value = 0

    async def async_added_to_hass(self) -> None:
        """Load the last known state when added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) and (
            last_number_data := await self.async_get_last_number_data()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._attr_native_value = last_number_data.native_value

        # Listen to memory writing events to update state if changed in ISY
        self._memory_change_handler = self._node.isy.nodes.status_events.subscribe(
            self.async_on_memory_write,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: DEV_MEMORY,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_memory_write(self, event: NodeChangedEvent, key: str) -> None:
        """Handle a memory write event from the ISY Node."""
        if not (BACKLIGHT_MEMORY_FILTER.items() <= event.event_info.items()):
            return  # This was not a backlight event
        value = ranged_value_to_percentage((0, 127), event.event_info["value"])
        if value == self._attr_native_value:
            return  # Change was from this entity, don't update twice
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""

        if not await self._node.send_cmd(
            CMD_BACKLIGHT, val=int(value), uom=UOM_PERCENTAGE
        ):
            raise HomeAssistantError(
                f"Could not set backlight to {value}% for {self._node.address}"
            )
        self._attr_native_value = value
        self.async_write_ha_state()
