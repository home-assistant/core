"""Remote entity proxies for sandboxed integrations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


@dataclass
class SandboxEntityDescription:
    """Description of a remote entity from a sandbox."""

    domain: str
    platform: str
    unique_id: str
    sandbox_id: str
    sandbox_entry_id: str
    device_id: str | None = None
    original_name: str | None = None
    original_icon: str | None = None
    entity_category: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    supported_features: int = 0
    capabilities: dict[str, Any] = field(default_factory=dict)
    has_entity_name: bool = False


class SandboxEntityManager:
    """Manages proxy entities for a sandbox connection."""

    def __init__(self, hass: HomeAssistant, sandbox_id: str) -> None:
        """Initialize the entity manager."""
        self.hass = hass
        self.sandbox_id = sandbox_id
        self._entities: dict[str, SandboxProxyEntity] = {}
        self._pending_calls: dict[str, asyncio.Future[Any]] = {}
        self._call_id_counter = 0

    @callback
    def add_entity(self, description: SandboxEntityDescription) -> SandboxProxyEntity:
        """Create a proxy entity (not yet tracked by entity_id)."""
        return _create_proxy_entity(description, self)

    @callback
    def track_entity(self, entity_id: str, entity: SandboxProxyEntity) -> None:
        """Track a proxy entity by its assigned entity_id."""
        self._entities[entity_id] = entity

    @callback
    def get_entity(self, entity_id: str) -> SandboxProxyEntity | None:
        """Get a proxy entity by entity_id."""
        return self._entities.get(entity_id)

    @callback
    def remove_entity(self, entity_id: str) -> None:
        """Remove a proxy entity."""
        self._entities.pop(entity_id, None)

    @callback
    def update_state(
        self, entity_id: str, state: str, attributes: dict[str, Any] | None
    ) -> None:
        """Update a proxy entity's state from sandbox push."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return
        entity.sandbox_update_state(state, attributes or {})

    @callback
    def mark_all_unavailable(self) -> None:
        """Mark all entities as unavailable (sandbox disconnected)."""
        for entity in self._entities.values():
            entity.sandbox_set_available(False)

    @callback
    def mark_all_available(self) -> None:
        """Mark all entities as available (sandbox reconnected)."""
        for entity in self._entities.values():
            entity.sandbox_set_available(True)

    def next_call_id(self) -> str:
        """Generate a unique call ID."""
        self._call_id_counter += 1
        return f"{self.sandbox_id}_{self._call_id_counter}"

    @callback
    def resolve_call(self, call_id: str, result: Any, error: str | None) -> None:
        """Resolve a pending method call from the sandbox."""
        future = self._pending_calls.pop(call_id, None)
        if future is None or future.done():
            return
        if error:
            future.set_exception(Exception(error))
        else:
            future.set_result(result)

    def create_call_future(self, call_id: str) -> asyncio.Future[Any]:
        """Create a future for a pending call."""
        future: asyncio.Future[Any] = self.hass.loop.create_future()
        self._pending_calls[call_id] = future
        return future


class SandboxProxyEntity(Entity):
    """Base class for proxy entities that live on the host."""

    _attr_should_poll = False

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy entity."""
        self._description = description
        self._manager = manager
        self._sandbox_available = True
        self._state_cache: dict[str, Any] = {}
        self._attr_unique_id = description.unique_id
        self._attr_has_entity_name = description.has_entity_name
        if description.original_name:
            self._attr_name = description.original_name
        if description.original_icon:
            self._attr_icon = description.original_icon
        if description.device_class:
            self._attr_device_class = description.device_class
        self._attr_supported_features = description.supported_features

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info to associate with the correct device."""
        if self._description.device_id is None:
            return None
        device_reg = dr.async_get(self.hass)
        device = device_reg.async_get(self._description.device_id)
        if device is None:
            return None
        return DeviceInfo(identifiers=device.identifiers)

    async def async_added_to_hass(self) -> None:
        """Register with entity manager once we have our entity_id."""
        self._manager.track_entity(self.entity_id, self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._sandbox_available

    @callback
    def sandbox_update_state(self, state: str, attributes: dict[str, Any]) -> None:
        """Update state from sandbox push."""
        self._state_cache.update(attributes)
        self._state_cache["state"] = state
        self.async_write_ha_state()

    @callback
    def sandbox_set_available(self, available: bool) -> None:
        """Set availability."""
        self._sandbox_available = available
        self.async_write_ha_state()

    async def _forward_method(self, method: str, **kwargs: Any) -> Any:
        """Forward a method call to the sandbox entity."""
        from ..const import DATA_SANDBOX

        sandbox_data = self.hass.data[DATA_SANDBOX]
        sandbox_info = sandbox_data.sandboxes.get(self._manager.sandbox_id)
        if sandbox_info is None or sandbox_info.send_command is None:
            raise RuntimeError("Sandbox not connected")

        call_id = self._manager.next_call_id()
        future = self._manager.create_call_future(call_id)

        sandbox_info.send_command(
            {
                "type": "call_method",
                "call_id": call_id,
                "entity_id": self.entity_id,
                "method": method,
                "kwargs": kwargs,
            }
        )

        return await asyncio.wait_for(future, timeout=30)


from .alarm_control_panel import SandboxAlarmControlPanelEntity
from .binary_sensor import SandboxBinarySensorEntity
from .button import SandboxButtonEntity
from .calendar import SandboxCalendarEntity
from .climate import SandboxClimateEntity
from .cover import SandboxCoverEntity
from .date import SandboxDateEntity
from .datetime import SandboxDateTimeEntity
from .device_tracker import SandboxScannerEntity, SandboxTrackerEntity
from .event import SandboxEventEntity
from .fan import SandboxFanEntity
from .humidifier import SandboxHumidifierEntity
from .lawn_mower import SandboxLawnMowerEntity
from .light import SandboxLightEntity
from .lock import SandboxLockEntity
from .media_player import SandboxMediaPlayerEntity
from .notify import SandboxNotifyEntity
from .number import SandboxNumberEntity
from .remote import SandboxRemoteEntity
from .scene import SandboxSceneEntity
from .select import SandboxSelectEntity
from .sensor import SandboxSensorEntity
from .siren import SandboxSirenEntity
from .switch import SandboxSwitchEntity
from .text import SandboxTextEntity
from .time import SandboxTimeEntity
from .todo import SandboxTodoListEntity
from .update import SandboxUpdateEntity
from .vacuum import SandboxVacuumEntity
from .valve import SandboxValveEntity
from .water_heater import SandboxWaterHeaterEntity
from .weather import SandboxWeatherEntity

_DOMAIN_ENTITY_MAP: dict[str, type[SandboxProxyEntity]] = {
    "alarm_control_panel": SandboxAlarmControlPanelEntity,
    "binary_sensor": SandboxBinarySensorEntity,
    "button": SandboxButtonEntity,
    "calendar": SandboxCalendarEntity,
    "climate": SandboxClimateEntity,
    "cover": SandboxCoverEntity,
    "date": SandboxDateEntity,
    "datetime": SandboxDateTimeEntity,
    "device_tracker": SandboxTrackerEntity,
    "event": SandboxEventEntity,
    "fan": SandboxFanEntity,
    "humidifier": SandboxHumidifierEntity,
    "lawn_mower": SandboxLawnMowerEntity,
    "light": SandboxLightEntity,
    "lock": SandboxLockEntity,
    "media_player": SandboxMediaPlayerEntity,
    "notify": SandboxNotifyEntity,
    "number": SandboxNumberEntity,
    "remote": SandboxRemoteEntity,
    "scene": SandboxSceneEntity,
    "select": SandboxSelectEntity,
    "sensor": SandboxSensorEntity,
    "siren": SandboxSirenEntity,
    "switch": SandboxSwitchEntity,
    "text": SandboxTextEntity,
    "time": SandboxTimeEntity,
    "todo": SandboxTodoListEntity,
    "update": SandboxUpdateEntity,
    "vacuum": SandboxVacuumEntity,
    "valve": SandboxValveEntity,
    "water_heater": SandboxWaterHeaterEntity,
    "weather": SandboxWeatherEntity,
}


def _create_proxy_entity(
    description: SandboxEntityDescription,
    manager: SandboxEntityManager,
) -> SandboxProxyEntity:
    """Create the appropriate proxy entity for the domain."""
    entity_cls = _DOMAIN_ENTITY_MAP.get(description.domain, SandboxProxyEntity)
    return entity_cls(description, manager)

__all__ = [
    "SandboxEntityDescription",
    "SandboxEntityManager",
    "SandboxProxyEntity",
    "_DOMAIN_ENTITY_MAP",
    "_create_proxy_entity",
]
