"""Shelly entity helper."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry, entity, entity_registry
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SLEEP_PERIOD, LOGGER
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .utils import (
    async_remove_shelly_entity,
    get_block_entity_name,
    get_rpc_entity_name,
    get_rpc_key_instances,
)


@callback
def async_setup_entry_attribute_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: Mapping[tuple[str, str], BlockEntityDescription],
    sensor_class: Callable,
    description_class: Callable[[RegistryEntry], BlockEntityDescription],
) -> None:
    """Set up entities for attributes."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].block
    assert coordinator
    if coordinator.device.initialized:
        async_setup_block_attribute_entities(
            hass, async_add_entities, coordinator, sensors, sensor_class
        )
    else:
        async_restore_block_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            coordinator,
            sensors,
            sensor_class,
            description_class,
        )


@callback
def async_setup_block_attribute_entities(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    coordinator: ShellyBlockCoordinator,
    sensors: Mapping[tuple[str, str], BlockEntityDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for block attributes."""
    blocks = []

    assert coordinator.device.blocks

    for block in coordinator.device.blocks:
        for sensor_id in block.sensor_ids:
            description = sensors.get((block.type, sensor_id))
            if description is None:
                continue

            # Filter out non-existing sensors and sensors without a value
            if getattr(block, sensor_id, None) in (-1, None):
                continue

            # Filter and remove entities that according to settings should not create an entity
            if description.removal_condition and description.removal_condition(
                coordinator.device.settings, block
            ):
                domain = sensor_class.__module__.split(".")[-1]
                unique_id = f"{coordinator.mac}-{block.description}-{sensor_id}"
                async_remove_shelly_entity(hass, domain, unique_id)
            else:
                blocks.append((block, sensor_id, description))

    if not blocks:
        return

    async_add_entities(
        [
            sensor_class(coordinator, block, sensor_id, description)
            for block, sensor_id, description in blocks
        ]
    )


@callback
def async_restore_block_attribute_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    coordinator: ShellyBlockCoordinator,
    sensors: Mapping[tuple[str, str], BlockEntityDescription],
    sensor_class: Callable,
    description_class: Callable[[RegistryEntry], BlockEntityDescription],
) -> None:
    """Restore block attributes entities."""
    entities = []

    ent_reg = entity_registry.async_get(hass)
    entries = entity_registry.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    )

    domain = sensor_class.__module__.split(".")[-1]

    for entry in entries:
        if entry.domain != domain:
            continue

        attribute = entry.unique_id.split("-")[-1]
        description = description_class(entry)

        entities.append(
            sensor_class(coordinator, None, attribute, description, entry, sensors)
        )

    if not entities:
        return

    async_add_entities(entities)


@callback
def async_setup_entry_rpc(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: Mapping[str, RpcEntityDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for RPC sensors."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
    assert coordinator

    if coordinator.device.initialized:
        async_setup_rpc_attribute_entities(
            hass, config_entry, async_add_entities, sensors, sensor_class
        )
    else:
        async_restore_rpc_attribute_entities(
            hass, config_entry, async_add_entities, coordinator, sensors, sensor_class
        )


@callback
def async_setup_rpc_attribute_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: Mapping[str, RpcEntityDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for RPC attributes."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
    assert coordinator

    if not (sleep_period := config_entry.data[CONF_SLEEP_PERIOD]):
        polling_coordinator = get_entry_data(hass)[config_entry.entry_id].rpc_poll
        assert polling_coordinator

    entities = []
    for sensor_id in sensors:
        description = sensors[sensor_id]
        key_instances = get_rpc_key_instances(
            coordinator.device.status, description.key
        )

        for key in key_instances:
            # Filter non-existing sensors
            if description.sub_key not in coordinator.device.status[
                key
            ] and not description.supported(coordinator.device.status[key]):
                continue

            # Filter and remove entities that according to settings/status should not create an entity
            if description.removal_condition and description.removal_condition(
                coordinator.device.config, coordinator.device.status, key
            ):
                domain = sensor_class.__module__.split(".")[-1]
                unique_id = f"{coordinator.mac}-{key}-{sensor_id}"
                async_remove_shelly_entity(hass, domain, unique_id)
            else:
                if description.use_polling_coordinator:
                    if not sleep_period:
                        entities.append(
                            sensor_class(
                                polling_coordinator, key, sensor_id, description
                            )
                        )
                else:
                    entities.append(
                        sensor_class(coordinator, key, sensor_id, description)
                    )
    if not entities:
        return

    async_add_entities(entities)


@callback
def async_restore_rpc_attribute_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    coordinator: ShellyRpcCoordinator,
    sensors: Mapping[str, RpcEntityDescription],
    sensor_class: Callable,
) -> None:
    """Restore block attributes entities."""
    entities = []

    ent_reg = entity_registry.async_get(hass)
    entries = entity_registry.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    )

    domain = sensor_class.__module__.split(".")[-1]

    for entry in entries:
        if entry.domain != domain:
            continue

        key = entry.unique_id.split("-")[-2]
        attribute = entry.unique_id.split("-")[-1]

        if description := sensors.get(attribute):
            entities.append(
                sensor_class(coordinator, key, attribute, description, entry)
            )

    if not entities:
        return

    async_add_entities(entities)


@callback
def async_setup_entry_rest(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: Mapping[str, RestEntityDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for REST sensors."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].rest
    assert coordinator

    async_add_entities(
        sensor_class(coordinator, sensor_id, sensors[sensor_id])
        for sensor_id in sensors
    )


@dataclass
class BlockEntityDescription(EntityDescription):
    """Class to describe a BLOCK entity."""

    icon_fn: Callable[[dict], str] | None = None
    unit_fn: Callable[[dict], str] | None = None
    value: Callable[[Any], Any] = lambda val: val
    available: Callable[[Block], bool] | None = None
    # Callable (settings, block), return true if entity should be removed
    removal_condition: Callable[[dict, Block], bool] | None = None
    extra_state_attributes: Callable[[Block], dict | None] | None = None


@dataclass
class RpcEntityRequiredKeysMixin:
    """Class for RPC entity required keys."""

    sub_key: str


@dataclass
class RpcEntityDescription(EntityDescription, RpcEntityRequiredKeysMixin):
    """Class to describe a RPC entity."""

    value: Callable[[Any, Any], Any] | None = None
    available: Callable[[dict], bool] | None = None
    removal_condition: Callable[[dict, dict, str], bool] | None = None
    extra_state_attributes: Callable[[dict, dict], dict | None] | None = None
    use_polling_coordinator: bool = False
    supported: Callable = lambda _: False


@dataclass
class RestEntityDescription(EntityDescription):
    """Class to describe a REST entity."""

    value: Callable[[dict, Any], Any] | None = None
    extra_state_attributes: Callable[[dict], dict | None] | None = None


class ShellyBlockEntity(CoordinatorEntity[ShellyBlockCoordinator]):
    """Helper class to represent a block entity."""

    def __init__(self, coordinator: ShellyBlockCoordinator, block: Block) -> None:
        """Initialize Shelly entity."""
        super().__init__(coordinator)
        self.block = block
        self._attr_name = get_block_entity_name(coordinator.device, block)
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            connections={(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._attr_unique_id = f"{coordinator.mac}-{block.description}"

    @property
    def available(self) -> bool:
        """Available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def set_state(self, **kwargs: Any) -> Any:
        """Set block state (HTTP request)."""
        LOGGER.debug("Setting state for entity %s, state: %s", self.name, kwargs)
        try:
            return await self.block.set_state(**kwargs)
        except DeviceConnectionError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                f"Setting state for entity {self.name} failed, state: {kwargs}, error: {repr(err)}"
            ) from err
        except InvalidAuthError:
            self.coordinator.entry.async_start_reauth(self.hass)


class ShellyRpcEntity(CoordinatorEntity[ShellyRpcCoordinator]):
    """Helper class to represent a rpc entity."""

    def __init__(self, coordinator: ShellyRpcCoordinator, key: str) -> None:
        """Initialize Shelly entity."""
        super().__init__(coordinator)
        self.key = key
        self._attr_should_poll = False
        self._attr_device_info = {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)}
        }
        self._attr_unique_id = f"{coordinator.mac}-{key}"
        self._attr_name = get_rpc_entity_name(coordinator.device, key)

    @property
    def available(self) -> bool:
        """Available."""
        return self.coordinator.last_update_success

    @property
    def status(self) -> dict:
        """Device status by entity key."""
        return cast(dict, self.coordinator.device.status[self.key])

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def call_rpc(self, method: str, params: Any) -> Any:
        """Call RPC method."""
        LOGGER.debug(
            "Call RPC for entity %s, method: %s, params: %s",
            self.name,
            method,
            params,
        )
        try:
            return await self.coordinator.device.call_rpc(method, params)
        except DeviceConnectionError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                f"Call RPC for {self.name} connection error, method: {method}, params: {params}, error: {repr(err)}"
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(
                f"Call RPC for {self.name} request error, method: {method}, params: {params}, error: {repr(err)}"
            ) from err
        except InvalidAuthError:
            self.coordinator.entry.async_start_reauth(self.hass)


class ShellyBlockAttributeEntity(ShellyBlockEntity, entity.Entity):
    """Helper class to represent a block attribute."""

    entity_description: BlockEntityDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, block)
        self.attribute = attribute
        self.entity_description = description

        self._attr_unique_id: str = f"{super().unique_id}-{self.attribute}"
        self._attr_name = get_block_entity_name(
            coordinator.device, block, description.name
        )

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if (value := getattr(self.block, self.attribute)) is None:
            return None

        return cast(StateType, self.entity_description.value(value))

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        if not available or not self.entity_description.available:
            return available

        return self.entity_description.available(self.block)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes is None:
            return None

        return self.entity_description.extra_state_attributes(self.block)


class ShellyRestAttributeEntity(CoordinatorEntity[ShellyBlockCoordinator]):
    """Class to load info from REST."""

    entity_description: RestEntityDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        attribute: str,
        description: RestEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.block_coordinator = coordinator
        self.attribute = attribute
        self.entity_description = description
        self._attr_name = get_block_entity_name(
            coordinator.device, None, description.name
        )
        self._attr_unique_id = f"{coordinator.mac}-{attribute}"
        self._attr_device_info = DeviceInfo(
            connections={(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._last_value = None

    @property
    def available(self) -> bool:
        """Available."""
        return self.block_coordinator.last_update_success

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if callable(self.entity_description.value):
            self._last_value = self.entity_description.value(
                self.block_coordinator.device.status, self._last_value
            )
        return self._last_value


class ShellyRpcAttributeEntity(ShellyRpcEntity, entity.Entity):
    """Helper class to represent a rpc attribute."""

    entity_description: RpcEntityDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key)
        self.attribute = attribute
        self.entity_description = description

        self._attr_unique_id = f"{super().unique_id}-{attribute}"
        self._attr_name = get_rpc_entity_name(coordinator.device, key, description.name)
        self._last_value = None

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if callable(self.entity_description.value):
            self._last_value = self.entity_description.value(
                self.coordinator.device.status[self.key].get(
                    self.entity_description.sub_key
                ),
                self._last_value,
            )
        else:
            self._last_value = self.coordinator.device.status[self.key][
                self.entity_description.sub_key
            ]

        return self._last_value

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        if not available or not self.entity_description.available:
            return available

        return self.entity_description.available(
            self.coordinator.device.status[self.key][self.entity_description.sub_key]
        )


class ShellySleepingBlockAttributeEntity(ShellyBlockAttributeEntity, RestoreEntity):
    """Represent a shelly sleeping block attribute entity."""

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockEntityDescription,
        entry: RegistryEntry | None = None,
        sensors: Mapping[tuple[str, str], BlockEntityDescription] | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        self.sensors = sensors
        self.last_state: StateType = None
        self.last_unit: str | None = None
        self.coordinator = coordinator
        self.attribute = attribute
        self.block: Block | None = block  # type: ignore[assignment]
        self.entity_description = description

        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            connections={(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

        if block is not None:
            self._attr_unique_id = (
                f"{self.coordinator.mac}-{block.description}-{attribute}"
            )
            self._attr_name = get_block_entity_name(
                self.coordinator.device, block, self.entity_description.name
            )
        elif entry is not None:
            self._attr_unique_id = entry.unique_id
            self._attr_name = cast(str, entry.original_name)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self.last_state = last_state.state
            self.last_unit = last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        if (
            self.block is not None
            or not self.coordinator.device.initialized
            or self.sensors is None
        ):
            super()._update_callback()
            return

        _, entity_block, entity_sensor = self._attr_unique_id.split("-")

        assert self.coordinator.device.blocks

        for block in self.coordinator.device.blocks:
            if block.description != entity_block:
                continue

            for sensor_id in block.sensor_ids:
                if sensor_id != entity_sensor:
                    continue

                description = self.sensors.get((block.type, sensor_id))
                if description is None:
                    continue

                self.block = block
                self.entity_description = description

                LOGGER.debug("Entity %s attached to block", self.name)
                super()._update_callback()
                return


class ShellySleepingRpcAttributeEntity(ShellyRpcAttributeEntity, RestoreEntity):
    """Helper class to represent a sleeping rpc attribute."""

    entity_description: RpcEntityDescription

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        self.last_state: StateType = None
        self.last_unit: str | None = None
        self.coordinator = coordinator
        self.key = key
        self.attribute = attribute
        self.entity_description = description

        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            connections={(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._attr_unique_id = (
            self._attr_unique_id
        ) = f"{coordinator.mac}-{key}-{attribute}"
        self._last_value = None

        if coordinator.device.initialized:
            self._attr_name = get_rpc_entity_name(
                coordinator.device, key, description.name
            )
        elif entry is not None:
            self._attr_name = cast(str, entry.original_name)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self.last_state = last_state.state
            self.last_unit = last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
