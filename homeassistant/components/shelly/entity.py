"""Shelly entity helper."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

from aioshelly.block_device import Block
import async_timeout

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry,
    entity,
    entity_registry,
    update_coordinator,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from . import BlockDeviceWrapper, RpcDeviceWrapper, ShellyDeviceRestWrapper
from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    BLOCK,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    REST,
    RPC,
)
from .utils import (
    async_remove_shelly_entity,
    get_block_entity_name,
    get_rpc_entity_name,
    get_rpc_key_instances,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_setup_entry_attribute_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: dict[tuple[str, str], BlockAttributeDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for attributes."""
    wrapper: BlockDeviceWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ][BLOCK]

    if wrapper.device.initialized:
        await async_setup_block_attribute_entities(
            hass, async_add_entities, wrapper, sensors, sensor_class
        )
    else:
        await async_restore_block_attribute_entities(
            hass, config_entry, async_add_entities, wrapper, sensors, sensor_class
        )


async def async_setup_block_attribute_entities(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    wrapper: BlockDeviceWrapper,
    sensors: dict[tuple[str, str], BlockAttributeDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for block attributes."""
    blocks = []

    assert wrapper.device.blocks

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
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    wrapper: BlockDeviceWrapper,
    sensors: dict[tuple[str, str], BlockAttributeDescription],
    sensor_class: Callable,
) -> None:
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

        entities.append(
            sensor_class(wrapper, None, attribute, description, entry, sensors)
        )

    if not entities:
        return

    async_add_entities(entities)


async def async_setup_entry_rpc(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: dict[str, RpcAttributeDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for REST sensors."""
    wrapper: RpcDeviceWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ][RPC]

    entities = []
    for sensor_id in sensors:
        description = sensors[sensor_id]
        key_instances = get_rpc_key_instances(wrapper.device.status, description.key)

        for key in key_instances:
            # Filter and remove entities that according to settings should not create an entity
            if description.removal_condition and description.removal_condition(
                wrapper.device.config, key
            ):
                domain = sensor_class.__module__.split(".")[-1]
                unique_id = f"{wrapper.mac}-{key}-{sensor_id}"
                await async_remove_shelly_entity(hass, domain, unique_id)
            else:
                entities.append((key, sensor_id, description))

    if not entities:
        return

    async_add_entities(
        [
            sensor_class(wrapper, key, sensor_id, description)
            for key, sensor_id, description in entities
        ]
    )


async def async_setup_entry_rest(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: dict[str, RestAttributeDescription],
    sensor_class: Callable,
) -> None:
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
    icon: str | None = None
    unit: None | str | Callable[[dict], str] = None
    value: Callable[[Any], Any] = lambda val: val
    device_class: str | None = None
    state_class: str | None = None
    default_enabled: bool = True
    available: Callable[[Block], bool] | None = None
    # Callable (settings, block), return true if entity should be removed
    removal_condition: Callable[[dict, Block], bool] | None = None
    extra_state_attributes: Callable[[Block], dict | None] | None = None


@dataclass
class RpcAttributeDescription:
    """Class to describe a RPC sensor."""

    key: str
    name: str
    icon: str | None = None
    unit: str | None = None
    value: Callable[[dict, Any], Any] | None = None
    device_class: str | None = None
    state_class: str | None = None
    default_enabled: bool = True
    available: Callable[[dict], bool] | None = None
    removal_condition: Callable[[dict, str], bool] | None = None
    extra_state_attributes: Callable[[dict], dict | None] | None = None


@dataclass
class RestAttributeDescription:
    """Class to describe a REST sensor."""

    name: str
    icon: str | None = None
    unit: str | None = None
    value: Callable[[dict, Any], Any] | None = None
    device_class: str | None = None
    state_class: str | None = None
    default_enabled: bool = True
    extra_state_attributes: Callable[[dict], dict | None] | None = None


class ShellyBlockEntity(entity.Entity):
    """Helper class to represent a block entity."""

    def __init__(self, wrapper: BlockDeviceWrapper, block: Block) -> None:
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.block = block
        self._name = get_block_entity_name(wrapper.device, block)

    @property
    def name(self) -> str:
        """Name of entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """If device should be polled."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def available(self) -> bool:
        """Available."""
        return self.wrapper.last_update_success

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.block.description}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self) -> None:
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def set_state(self, **kwargs: Any) -> Any:
        """Set block state (HTTP request)."""
        _LOGGER.debug("Setting state for entity %s, state: %s", self.name, kwargs)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.block.set_state(**kwargs)
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.error(
                "Setting state for entity %s failed, state: %s, error: %s",
                self.name,
                kwargs,
                repr(err),
            )
            self.wrapper.last_update_success = False
            return None


class ShellyRpcEntity(entity.Entity):
    """Helper class to represent a rpc entity."""

    def __init__(self, wrapper: RpcDeviceWrapper, key: str) -> None:
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.key = key
        self._attr_should_poll = False
        self._attr_device_info = {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, wrapper.mac)}
        }
        self._attr_unique_id = f"{wrapper.mac}-{key}"
        self._attr_name = get_rpc_entity_name(wrapper.device, key)

    @property
    def available(self) -> bool:
        """Available."""
        return self.wrapper.device.connected

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self) -> None:
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def call_rpc(self, method: str, params: Any) -> Any:
        """Call RPC method."""
        _LOGGER.debug(
            "Call RPC for entity %s, method: %s, params: %s",
            self.name,
            method,
            params,
        )
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.wrapper.device.call_rpc(method, params)
        except asyncio.TimeoutError as err:
            _LOGGER.error(
                "Call RPC for entity %s failed, method: %s, params: %s, error: %s",
                self.name,
                method,
                params,
                repr(err),
            )
            self.wrapper.last_update_success = False
            return None


class ShellyBlockAttributeEntity(ShellyBlockEntity, entity.Entity):
    """Helper class to represent a block attribute."""

    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        block: Block,
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

        self._unit: None | str | Callable[[dict], str] = unit
        self._unique_id: str = f"{super().unique_id}-{self.attribute}"
        self._name = get_block_entity_name(wrapper.device, block, self.description.name)

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Name of sensor."""
        return self._name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if it should be enabled by default."""
        return self.description.default_enabled

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        value = getattr(self.block, self.attribute)

        if value is None:
            return None

        return cast(StateType, self.description.value(value))

    @property
    def device_class(self) -> str | None:
        """Device class of sensor."""
        return self.description.device_class

    @property
    def icon(self) -> str | None:
        """Icon of sensor."""
        return self.description.icon

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        if not available or not self.description.available:
            return available

        return self.description.available(self.block)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.description.extra_state_attributes is None:
            return None

        return self.description.extra_state_attributes(self.block)


class ShellyRestAttributeEntity(update_coordinator.CoordinatorEntity):
    """Class to load info from REST."""

    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        attribute: str,
        description: RestAttributeDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper)
        self.wrapper = wrapper
        self.attribute = attribute
        self.description = description
        self._name = get_block_entity_name(wrapper.device, None, self.description.name)
        self._last_value = None

    @property
    def name(self) -> str:
        """Name of sensor."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if it should be enabled by default."""
        return self.description.default_enabled

    @property
    def available(self) -> bool:
        """Available."""
        return self.wrapper.last_update_success

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if callable(self.description.value):
            self._last_value = self.description.value(
                self.wrapper.device.status, self._last_value
            )
        return self._last_value

    @property
    def device_class(self) -> str | None:
        """Device class of sensor."""
        return self.description.device_class

    @property
    def icon(self) -> str | None:
        """Icon of sensor."""
        return self.description.icon

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.attribute}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.description.extra_state_attributes is None:
            return None

        return self.description.extra_state_attributes(self.wrapper.device.status)


class ShellyRpcAttributeEntity(ShellyRpcEntity, entity.Entity):
    """Helper class to represent a rpc attribute."""

    def __init__(
        self,
        wrapper: RpcDeviceWrapper,
        key: str,
        attribute: str,
        description: RpcAttributeDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, key)
        self.attribute = attribute
        self.description = description

        self._attr_unique_id = f"{super().unique_id}-{attribute}"
        self._attr_name = get_rpc_entity_name(wrapper.device, key, description.name)
        self._attr_entity_registry_enabled_default = description.default_enabled
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon
        self._last_value = None

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if callable(self.description.value):
            self._last_value = self.description.value(
                self.wrapper.device.status[self.key], self._last_value
            )
        return self._last_value

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        if not available or not self.description.available:
            return available

        return self.description.available(self.wrapper.device.status[self.key])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.description.extra_state_attributes is None:
            return None

        return self.description.extra_state_attributes(
            self.wrapper.device.status[self.key]
        )


class ShellySleepingBlockAttributeEntity(ShellyBlockAttributeEntity, RestoreEntity):
    """Represent a shelly sleeping block attribute entity."""

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        block: Block | None,
        attribute: str,
        description: BlockAttributeDescription,
        entry: entity_registry.RegistryEntry | None = None,
        sensors: dict[tuple[str, str], BlockAttributeDescription] | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        self.sensors = sensors
        self.last_state: StateType = None
        self.wrapper = wrapper
        self.attribute = attribute
        self.block: Block | None = block  # type: ignore[assignment]
        self.description = description
        self._unit = self.description.unit

        if block is not None:
            if callable(self._unit):
                self._unit = self._unit(block.info(attribute))

            self._unique_id = f"{self.wrapper.mac}-{block.description}-{attribute}"
            self._name = get_block_entity_name(
                self.wrapper.device, block, self.description.name
            )
        elif entry is not None:
            self._unique_id = entry.unique_id
            self._name = cast(str, entry.original_name)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self.last_state = last_state.state
            self.description.state_class = last_state.attributes.get(ATTR_STATE_CLASS)

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        if (
            self.block is not None
            or not self.wrapper.device.initialized
            or self.sensors is None
        ):
            super()._update_callback()
            return

        _, entity_block, entity_sensor = self.unique_id.split("-")

        assert self.wrapper.device.blocks

        for block in self.wrapper.device.blocks:
            if block.description != entity_block:
                continue

            for sensor_id in block.sensor_ids:
                if sensor_id != entity_sensor:
                    continue

                description = self.sensors.get((block.type, sensor_id))
                if description is None:
                    continue

                self.block = block
                self.description = description

                _LOGGER.debug("Entity %s attached to block", self.name)
                super()._update_callback()
                return
