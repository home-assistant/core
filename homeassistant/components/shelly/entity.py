"""Shelly entity helper."""
from dataclasses import dataclass
import logging
from typing import Any, Callable, Optional, Union

import aioshelly

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import (
    device_registry,
    entity,
    entity_registry,
    update_coordinator,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import ShellyDeviceRestWrapper, ShellyDeviceWrapper
from .const import COAP, DATA_CONFIG_ENTRY, DOMAIN, REST
from .utils import async_remove_shelly_entity, get_entity_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry_attribute_entities(
    hass, config_entry, async_add_entities, sensors, sensor_class
):
    """Set up entities for attributes."""
    wrapper: ShellyDeviceWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ][COAP]

    if wrapper.device.initialized:
        await async_setup_block_attribute_entities(
            hass, async_add_entities, wrapper, sensors, sensor_class
        )
    else:
        await async_restore_block_attribute_entities(
            hass, config_entry, async_add_entities, wrapper, sensor_class
        )


async def async_setup_block_attribute_entities(
    hass, async_add_entities, wrapper, sensors, sensor_class
):
    """Set up entities for block attributes."""
    blocks = []

    for block in wrapper.device.blocks:
        for sensor_id in block.sensor_ids:
            description = sensors.get((block.type, sensor_id))
            if description is None:
                continue

            # Filter out non-existing sensors and sensors without a value
            if getattr(block, sensor_id, None) in (-1, None):
                continue

            # Filter and remove entities that according to settings should not create an entity
            if description.removal_condition and description.removal_condition(
                wrapper.device.settings, block
            ):
                domain = sensor_class.__module__.split(".")[-1]
                unique_id = f"{wrapper.mac}-{block.description}-{sensor_id}"
                await async_remove_shelly_entity(hass, domain, unique_id)
            else:
                blocks.append((block, sensor_id, description))

    if not blocks:
        return

    async_add_entities(
        [
            sensor_class(wrapper, block, sensor_id, description)
            for block, sensor_id, description in blocks
        ]
    )


async def async_restore_block_attribute_entities(
    hass, config_entry, async_add_entities, wrapper, sensor_class
):
    """Restore block attributes entities."""
    entities = []

    ent_reg = await entity_registry.async_get_registry(hass)
    entries = entity_registry.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    )

    domain = sensor_class.__module__.split(".")[-1]

    for entry in entries:
        if entry.domain != domain:
            continue

        attribute = entry.unique_id.split("-")[-1]
        description = BlockAttributeDescription(
            name="",
            icon=entry.original_icon,
            unit=entry.unit_of_measurement,
            device_class=entry.device_class,
        )

        entities.append(sensor_class(wrapper, None, attribute, description, entry))

    if not entities:
        return

    async_add_entities(entities)


async def async_setup_entry_rest(
    hass, config_entry, async_add_entities, sensors, sensor_class
):
    """Set up entities for REST sensors."""
    wrapper: ShellyDeviceRestWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ][REST]

    entities = []
    for sensor_id in sensors:
        description = sensors.get(sensor_id)

        if not wrapper.device.settings.get("sleep_mode"):
            entities.append((sensor_id, description))

    if not entities:
        return

    async_add_entities(
        [
            sensor_class(wrapper, sensor_id, description)
            for sensor_id, description in entities
        ]
    )


@dataclass
class BlockAttributeDescription:
    """Class to describe a sensor."""

    name: str
    # Callable = lambda attr_info: unit
    icon: Optional[str] = None
    unit: Union[None, str, Callable[[dict], str]] = None
    value: Callable[[Any], Any] = lambda val: val
    device_class: Optional[str] = None
    default_enabled: bool = True
    available: Optional[Callable[[aioshelly.Block], bool]] = None
    # Callable (settings, block), return true if entity should be removed
    removal_condition: Optional[Callable[[dict, aioshelly.Block], bool]] = None
    device_state_attributes: Optional[
        Callable[[aioshelly.Block], Optional[dict]]
    ] = None


@dataclass
class RestAttributeDescription:
    """Class to describe a REST sensor."""

    name: str
    icon: Optional[str] = None
    unit: Optional[str] = None
    value: Callable[[dict, Any], Any] = None
    device_class: Optional[str] = None
    default_enabled: bool = True
    device_state_attributes: Optional[Callable[[dict], Optional[dict]]] = None


class ShellyBlockEntity(entity.Entity):
    """Helper class to represent a block."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block):
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.block = block
        self._name = get_entity_name(wrapper.device, block)

    @property
    def name(self):
        """Name of entity."""
        return self._name

    @property
    def should_poll(self):
        """If device should be polled."""
        return False

    @property
    def device_info(self):
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def available(self):
        """Available."""
        return self.wrapper.last_update_success

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.block.description}"

    async def async_added_to_hass(self):
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self):
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self):
        """Handle device update."""
        self.async_write_ha_state()


class ShellyBlockAttributeEntity(ShellyBlockEntity, entity.Entity):
    """Helper class to represent a block attribute."""

    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        block: aioshelly.Block,
        attribute: str,
        description: BlockAttributeDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, block)
        self.attribute = attribute
        self.description = description

        unit = self.description.unit

        if callable(unit):
            unit = unit(block.info(attribute))

        self._unit = unit
        self._unique_id = f"{super().unique_id}-{self.attribute}"
        self._name = get_entity_name(wrapper.device, block, self.description.name)

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self):
        """Name of sensor."""
        return self._name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if it should be enabled by default."""
        return self.description.default_enabled

    @property
    def attribute_value(self):
        """Value of sensor."""
        value = getattr(self.block, self.attribute)

        if value is None:
            return None

        return self.description.value(value)

    @property
    def unit_of_measurement(self):
        """Return unit of sensor."""
        return self._unit

    @property
    def device_class(self):
        """Device class of sensor."""
        return self.description.device_class

    @property
    def icon(self):
        """Icon of sensor."""
        return self.description.icon

    @property
    def available(self):
        """Available."""
        available = super().available

        if not available or not self.description.available:
            return available

        return self.description.available(self.block)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.description.device_state_attributes is None:
            return None

        return self.description.device_state_attributes(self.block)


class ShellyRestAttributeEntity(update_coordinator.CoordinatorEntity):
    """Class to load info from REST."""

    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        attribute: str,
        description: RestAttributeDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper)
        self.wrapper = wrapper
        self.attribute = attribute
        self.description = description
        self._name = get_entity_name(wrapper.device, None, self.description.name)
        self._last_value = None

    @property
    def name(self):
        """Name of sensor."""
        return self._name

    @property
    def device_info(self):
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if it should be enabled by default."""
        return self.description.default_enabled

    @property
    def available(self):
        """Available."""
        return self.wrapper.last_update_success

    @property
    def attribute_value(self):
        """Value of sensor."""
        self._last_value = self.description.value(
            self.wrapper.device.status, self._last_value
        )
        return self._last_value

    @property
    def unit_of_measurement(self):
        """Return unit of sensor."""
        return self.description.unit

    @property
    def device_class(self):
        """Device class of sensor."""
        return self.description.device_class

    @property
    def icon(self):
        """Icon of sensor."""
        return self.description.icon

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.attribute}"

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self.description.device_state_attributes is None:
            return None

        return self.description.device_state_attributes(self.wrapper.device.status)


class ShellySleepingBlockAttributeEntity(ShellyBlockAttributeEntity, RestoreEntity):
    """Represent a shelly sleeping block attribute entity."""

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        block: aioshelly.Block,
        attribute: str,
        description: BlockAttributeDescription,
        entry: Optional[ConfigEntry] = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        self.last_state = None
        self.wrapper = wrapper
        self.attribute = attribute
        self.block = block
        self.description = description
        self._unit = self.description.unit

        if block is not None:
            if callable(self._unit):
                self._unit = self._unit(block.info(attribute))

            self._unique_id = f"{self.wrapper.mac}-{block.description}-{attribute}"
            self._name = get_entity_name(
                self.wrapper.device, block, self.description.name
            )
        else:
            self._unique_id = entry.unique_id
            self._name = entry.original_name

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self.last_state = last_state.state

    @callback
    def _update_callback(self):
        """Handle device update."""
        if self.block is not None:
            super()._update_callback()
            return

        _, entity_block, entity_sensor = self.unique_id.split("-")

        for block in self.wrapper.device.blocks:
            if block.description != entity_block:
                continue

            for sensor_id in block.sensor_ids:
                if sensor_id != entity_sensor:
                    continue

                self.block = block
                _LOGGER.debug("Entity %s attached to block", self.name)
                super()._update_callback()
                return
