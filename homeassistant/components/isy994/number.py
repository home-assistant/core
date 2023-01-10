"""Support for ISY number entities."""
from __future__ import annotations

from typing import Any

from pyisy import ISY
from pyisy.helpers import EventListener, NodeProperty
from pyisy.variables import Variable

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _async_isy_to_configuration_url
from .const import (
    DOMAIN as ISY994_DOMAIN,
    ISY_CONF_FIRMWARE,
    ISY_CONF_MODEL,
    ISY_CONF_NAME,
    ISY_CONF_UUID,
    ISY_ROOT,
    ISY_VARIABLES,
    MANUFACTURER,
)
from .helpers import convert_isy_value_to_hass

ISY_MAX_SIZE = (2**32) / 2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX number entities from config entry."""
    hass_isy_data = hass.data[ISY994_DOMAIN][config_entry.entry_id]
    isy: ISY = hass_isy_data[ISY_ROOT]
    uuid = isy.configuration[ISY_CONF_UUID]
    entities: list[ISYVariableNumberEntity] = []

    for node, enable_by_default in hass_isy_data[ISY_VARIABLES][Platform.NUMBER]:
        step = 10 ** (-1 * node.prec)
        min_max = ISY_MAX_SIZE / (10**node.prec)
        description = NumberEntityDescription(
            key=node.address,
            name=node.name,
            icon="mdi:counter",
            entity_registry_enabled_default=enable_by_default,
            native_unit_of_measurement=None,
            native_step=step,
            native_min_value=-min_max,
            native_max_value=min_max,
        )
        description_init = NumberEntityDescription(
            key=f"{node.address}_init",
            name=f"{node.name} Initial Value",
            icon="mdi:counter",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=None,
            native_step=step,
            native_min_value=-min_max,
            native_max_value=min_max,
            entity_category=EntityCategory.CONFIG,
        )

        entities.append(
            ISYVariableNumberEntity(
                node,
                unique_id=f"{uuid}_{node.address}",
                description=description,
            )
        )
        entities.append(
            ISYVariableNumberEntity(
                node=node,
                unique_id=f"{uuid}_{node.address}_init",
                description=description_init,
                init_entity=True,
            )
        )

    async_add_entities(entities)


class ISYVariableNumberEntity(NumberEntity):
    """Representation of an ISY variable as a number entity device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _init_entity: bool
    _node: Variable
    entity_description: NumberEntityDescription

    def __init__(
        self,
        node: Variable,
        unique_id: str,
        description: NumberEntityDescription,
        init_entity: bool = False,
    ) -> None:
        """Initialize the ISY variable number."""
        self._node = node
        self._name = description.name
        self.entity_description = description
        self._change_handler: EventListener | None = None

        # Two entities are created for each variable, one for current value and one for initial.
        # Initial value entities are disabled by default
        self._init_entity = init_entity

        self._attr_unique_id = unique_id

        url = _async_isy_to_configuration_url(node.isy)
        config = node.isy.configuration
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    ISY994_DOMAIN,
                    f"{config[ISY_CONF_UUID]}_variables",
                )
            },
            manufacturer=MANUFACTURER,
            name=f"{config[ISY_CONF_NAME]} Variables",
            model=config[ISY_CONF_MODEL],
            sw_version=config[ISY_CONF_FIRMWARE],
            configuration_url=url,
            via_device=(ISY994_DOMAIN, config[ISY_CONF_UUID]),
            entry_type=DeviceEntryType.SERVICE,
        )

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
