"""Refoss entity helper."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from aiorefoss.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import LOGGER
from .coordinator import RefossConfigEntry, RefossCoordinator
from .utils import (
    async_remove_refoss_entity,
    get_refoss_entity_name,
    get_refoss_key_instances,
)


@callback
def async_setup_entry_refoss(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: Mapping[str, RefossEntityDescription],
    sensor_class: Callable,
) -> None:
    """Set up entities for  Refoss."""
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator
    if not coordinator.device.initialized:
        return

    polling_coordinator = config_entry.runtime_data.poll_coordinator

    entities = []
    for sensor_id in sensors:
        description = sensors[sensor_id]
        key_instances = get_refoss_key_instances(
            coordinator.device.status, description.key
        )

        for key in key_instances:
            # Filter non-existing sensors
            if description.sub_key not in coordinator.device.status[
                key
            ] and not description.supported(coordinator.device.status[key]):
                continue

            # Filter and remove entities that according to settings/status
            # should not create an entity
            if description.removal_condition and description.removal_condition(
                coordinator.device.config, coordinator.device.status, key
            ):
                domain = sensor_class.__module__.split(".")[-1]
                unique_id = f"{coordinator.mac}-{key}-{sensor_id}"
                async_remove_refoss_entity(hass, domain, unique_id)
            elif description.use_polling_coordinator:
                entities.append(
                    sensor_class(polling_coordinator, key, sensor_id, description)
                )
            else:
                entities.append(sensor_class(coordinator, key, sensor_id, description))
    if not entities:
        return

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class RefossEntityDescription(EntityDescription):
    """Class to describe a  entity."""

    name: str = ""
    sub_key: str

    value: Callable[[Any, Any], Any] | None = None
    removal_condition: Callable[[dict, dict, str], bool] | None = None
    use_polling_coordinator: bool = False
    supported: Callable = lambda _: False


class RefossEntity(CoordinatorEntity[RefossCoordinator]):
    """Helper class to represent a entity."""

    def __init__(self, coordinator: RefossCoordinator, key: str) -> None:
        """Initialize Refoss entity."""
        super().__init__(coordinator)
        self.key = key
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._attr_unique_id = f"{coordinator.mac}-{key}"
        self._attr_name = get_refoss_entity_name(coordinator.device, key)

    @property
    def available(self) -> bool:
        """Check if device is available and initialized."""
        coordinator = self.coordinator
        return super().available and (coordinator.device.initialized)

    @property
    def status(self) -> dict:
        """Device status by entity key."""
        return cast(dict, self.coordinator.device.status[self.key])

    # pylint: disable-next=hass-missing-super-call
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
                f"Call RPC for {self.name} connection error, method: {method}, params:"
                f" {params}, error: {err!r}"
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(
                f"Call RPC for {self.name} request error, method: {method}, params:"
                f" {params}, error: {err!r}"
            ) from err
        except InvalidAuthError:
            await self.coordinator.async_shutdown_device_and_start_reauth()


class RefossAttributeEntity(RefossEntity, Entity):
    """Helper class to represent a attribute."""

    entity_description: RefossEntityDescription

    def __init__(
        self,
        coordinator: RefossCoordinator,
        key: str,
        attribute: str,
        description: RefossEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key)
        self.attribute = attribute
        self.entity_description = description

        self._attr_unique_id = f"{super().unique_id}-{attribute}"
        self._attr_name = get_refoss_entity_name(
            device=coordinator.device, key=key, description=description.name
        )
        self._last_value = None

    @property
    def sub_status(self) -> Any:
        """Device status by entity key."""
        return self.status[self.entity_description.sub_key]

    @property
    def attribute_value(self) -> StateType:
        """Value of sensor."""
        if self.entity_description.value is not None:
            self._last_value = self.entity_description.value(
                self.status.get(self.entity_description.sub_key), self._last_value
            )
        else:
            self._last_value = self.sub_status

        return self._last_value
