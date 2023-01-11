"""Support for ISY number entities."""
from __future__ import annotations

from typing import cast

from pyisy import ISY
from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    ISY_VALUE_UNKNOWN,
    PROP_RAMP_RATE,
    UOM_TO_STATES,
)
from pyisy.helpers import NodeProperty

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, INSTEON_RAMP_RATES, UOM_INDEX
from .entity import ISYAuxControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX select entities from config entry."""
    isy_data = hass.data[DOMAIN][config_entry.entry_id]
    isy: ISY = isy_data.root
    device_info = isy_data.devices
    entities: list[ISYAuxControlSelectEntity] = []

    for node, control in isy_data.aux_properties[Platform.SELECT]:
        name = COMMAND_FRIENDLY_NAME.get(control, control).replace("_", " ").title()
        if node.address != node.primary_node:
            name = f"{node.name} {name}"

        node_prop: NodeProperty = node.aux_properties[control]

        options = []
        if control == PROP_RAMP_RATE:
            options = INSTEON_RAMP_RATES
        elif node_prop.uom == UOM_INDEX:
            if options_dict := UOM_TO_STATES.get(node_prop.uom):
                options = options_dict.values()

        description = SelectEntityDescription(
            key=f"{node.address}_{control}",
            name=name,
            entity_category=EntityCategory.CONFIG,
            options=options,
        )

        entities.append(
            ISYAuxControlSelectEntity(
                node=node,
                control=control,
                unique_id=f"{isy.uuid}_{node.address}_{control}",
                description=description,
                device_info=device_info.get(node.primary_node),
            )
        )
    async_add_entities(entities)


class ISYAuxControlSelectEntity(ISYAuxControlEntity, SelectEntity):
    """Representation of a ISY/IoX Aux Control Select entity."""

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]
        if node_prop.value == ISY_VALUE_UNKNOWN:
            return None

        if self._control == PROP_RAMP_RATE:
            return INSTEON_RAMP_RATES[int(node_prop.value)]
        if node_prop.uom == UOM_INDEX:
            if options_dict := UOM_TO_STATES.get(node_prop.uom):
                return cast(str, options_dict.get(node_prop.value, node_prop.value))
        return cast(str, node_prop.formatted)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]

        if self._control == PROP_RAMP_RATE:
            await self._node.set_ramp_rate(INSTEON_RAMP_RATES.index(option))
            return
        if node_prop.uom == UOM_INDEX:
            await self._node.send_cmd(
                self._control, val=self.options.index(option), uom=node_prop.uom
            )
