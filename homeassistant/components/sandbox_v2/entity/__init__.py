"""Per-domain proxy entities for sandboxed integrations.

The :class:`SandboxProxyEntity` base holds the cached state and the
``async_call_service`` plumbing every proxy shares. Domain-specific
subclasses add typed properties that pull values out of the cache so
service-handler kwarg filtering (``light.filter_turn_on_params``,
``climate`` schema validation, …) and frontend rendering see the same
shape they would for a local entity.

Phase 5 ships proxies for the small "rich" set the spike and tests
exercise. The remaining domains from the v1 list use the same mechanical
pattern — see ``plan.md`` Phase 5's deferral note.
"""

import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


class SandboxProxyEntity(Entity):
    """Base class for proxy entities backed by a sandboxed entity."""

    _attr_should_poll = False

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Initialise the proxy entity from its sandbox-side description."""
        self._bridge = bridge
        self.description = description
        self._state_cache: dict[str, Any] = dict(description.initial_attributes)
        if description.initial_state is not None:
            self._state_cache["state"] = description.initial_state
        self._sandbox_available: bool = True

        self._attr_unique_id = description.unique_id
        self._attr_has_entity_name = description.has_entity_name
        if description.name:
            self._attr_name = description.name
        if description.icon:
            self._attr_icon = description.icon
        if description.entity_category:
            with contextlib.suppress(ValueError):
                self._attr_entity_category = EntityCategory(description.entity_category)
        if description.device_class:
            self._attr_device_class = description.device_class
        # Domains like ``light`` index supported_features with bitwise
        # ``in``; ``None`` blows up the check, so default to 0.
        self._attr_supported_features = int(description.supported_features or 0)

    @property
    def available(self) -> bool:
        """Available iff the sandbox is reachable and the entity has state."""
        if not self._sandbox_available:
            return False
        state = self._state_cache.get("state")
        return state not in (None, "unavailable")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Sandbox proxies expose attributes through typed properties.

        Anything domain-specific (``brightness``, ``hvac_mode``, …) is
        surfaced by the domain proxy's own ``@property`` declarations
        reading from ``_state_cache``. Returning extras here would
        duplicate those values in the state-machine attributes dict.
        """
        return None

    def sandbox_apply_state(
        self, state: str | None, attributes: dict[str, Any]
    ) -> None:
        """Update the cache from a sandbox push, and notify HA."""
        self._state_cache = dict(attributes)
        if state is not None:
            self._state_cache["state"] = state
        if self.hass is not None:
            self.async_write_ha_state()

    def sandbox_set_available(self, available: bool) -> None:
        """Toggle availability — used when the sandbox channel drops."""
        if self._sandbox_available == available:
            return
        self._sandbox_available = available
        if self.hass is not None:
            self.async_write_ha_state()

    async def _call_service(self, service: str, **service_data: Any) -> Any:
        """Forward a service call to the sandbox.

        Domain proxies translate each entity method into one of these
        calls (the spike's Option B). The bridge coalesces calls made in
        the same tick into a single multi-entity RPC.
        """
        return await self._bridge.async_call_service(
            domain=self.description.domain,
            service=service,
            sandbox_entity_id=self.description.sandbox_entity_id,
            service_data=service_data,
        )


# Lazy import to avoid a circular dependency at module import time
# (bridge imports build_proxy → entity imports proxies → proxies import
# the domain platform; the domain platforms can import sandbox_v2
# indirectly via helpers).
def build_proxy(
    bridge: SandboxBridge, description: SandboxEntityDescription
) -> SandboxProxyEntity:
    """Return the domain-specific proxy class for ``description.domain``."""
    cls = _DOMAIN_PROXIES.get(description.domain, SandboxProxyEntity)
    return cls(bridge, description)


def _build_registry() -> dict[str, type[SandboxProxyEntity]]:
    """Lazy-build the domain → proxy-class map.

    Importing every domain proxy eagerly at module import time would force
    every domain platform module (``homeassistant.components.light``, …)
    to load on integration boot. Hand-rolled to avoid the import storm.
    """
    from . import (  # noqa: PLC0415
        alarm_control_panel,
        binary_sensor,
        button,
        calendar,
        climate,
        cover,
        date,
        datetime,
        device_tracker,
        event,
        fan,
        humidifier,
        lawn_mower,
        light,
        lock,
        media_player,
        notify,
        number,
        remote,
        scene,
        select,
        sensor,
        siren,
        switch,
        text,
        time,
        todo,
        update,
        vacuum,
        valve,
        water_heater,
        weather,
    )

    return {
        "alarm_control_panel": alarm_control_panel.SandboxAlarmControlPanelEntity,
        "binary_sensor": binary_sensor.SandboxBinarySensorEntity,
        "button": button.SandboxButtonEntity,
        "calendar": calendar.SandboxCalendarEntity,
        "climate": climate.SandboxClimateEntity,
        "cover": cover.SandboxCoverEntity,
        "date": date.SandboxDateEntity,
        "datetime": datetime.SandboxDateTimeEntity,
        "device_tracker": device_tracker.SandboxDeviceTrackerEntity,
        "event": event.SandboxEventEntity,
        "fan": fan.SandboxFanEntity,
        "humidifier": humidifier.SandboxHumidifierEntity,
        "lawn_mower": lawn_mower.SandboxLawnMowerEntity,
        "light": light.SandboxLightEntity,
        "lock": lock.SandboxLockEntity,
        "media_player": media_player.SandboxMediaPlayerEntity,
        "notify": notify.SandboxNotifyEntity,
        "number": number.SandboxNumberEntity,
        "remote": remote.SandboxRemoteEntity,
        "scene": scene.SandboxSceneEntity,
        "select": select.SandboxSelectEntity,
        "sensor": sensor.SandboxSensorEntity,
        "siren": siren.SandboxSirenEntity,
        "switch": switch.SandboxSwitchEntity,
        "text": text.SandboxTextEntity,
        "time": time.SandboxTimeEntity,
        "todo": todo.SandboxTodoListEntity,
        "update": update.SandboxUpdateEntity,
        "vacuum": vacuum.SandboxVacuumEntity,
        "valve": valve.SandboxValveEntity,
        "water_heater": water_heater.SandboxWaterHeaterEntity,
        "weather": weather.SandboxWeatherEntity,
    }


_DOMAIN_PROXIES: dict[str, type[SandboxProxyEntity]] = _build_registry()


__all__ = [
    "SandboxProxyEntity",
    "build_proxy",
]
