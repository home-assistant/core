"""Remote entity proxies for sandboxed integrations.

When a sandbox registers entities, the sandbox integration creates proxy
Entity instances on the host. These proxies:
- Are added to the domain's EntityComponent via a real EntityPlatform
- Cache state/attributes received from the sandbox
- Forward service calls (turn_on, etc.) to the sandbox via websocket
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.components.date import DateEntity
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.components.event import EventEntity
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature
from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.components.scene import Scene
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.components.time import TimeEntity
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
        self._platform_add_callbacks: dict[str, AddEntitiesCallback] = {}
        self._call_id_counter = 0

    @callback
    def register_platform_callback(
        self, domain: str, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Register the async_add_entities callback for a domain."""
        self._platform_add_callbacks[domain] = async_add_entities

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
        from .const import DATA_SANDBOX

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


class SandboxLightEntity(SandboxProxyEntity, LightEntity):
    """Proxy for a light entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy light entity."""
        super().__init__(description, manager)
        from homeassistant.components.light import LightEntityFeature

        self._attr_supported_features = LightEntityFeature(
            description.supported_features
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the light is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def brightness(self) -> int | None:
        """Return the brightness."""
        return self._state_cache.get(ATTR_BRIGHTNESS)

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode."""
        return self._state_cache.get(ATTR_COLOR_MODE)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color."""
        val = self._state_cache.get(ATTR_HS_COLOR)
        return tuple(val) if val else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color."""
        val = self._state_cache.get(ATTR_RGB_COLOR)
        return tuple(val) if val else None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color."""
        val = self._state_cache.get(ATTR_RGBW_COLOR)
        return tuple(val) if val else None

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the RGBWW color."""
        val = self._state_cache.get(ATTR_RGBWW_COLOR)
        return tuple(val) if val else None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the XY color."""
        val = self._state_cache.get(ATTR_XY_COLOR)
        return tuple(val) if val else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return self._state_cache.get(ATTR_COLOR_TEMP_KELVIN)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the min color temperature."""
        return self._description.capabilities.get(
            ATTR_MIN_COLOR_TEMP_KELVIN, 2000
        )

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the max color temperature."""
        return self._description.capabilities.get(
            ATTR_MAX_COLOR_TEMP_KELVIN, 6500
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state_cache.get(ATTR_EFFECT)

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._description.capabilities.get(ATTR_EFFECT_LIST)

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Return the supported color modes."""
        modes = self._description.capabilities.get(ATTR_SUPPORTED_COLOR_MODES)
        if modes is None:
            return None
        return {ColorMode(m) for m in modes}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)


class SandboxBinarySensorEntity(SandboxProxyEntity, BinarySensorEntity):
    """Proxy for a binary_sensor entity in a sandbox."""

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"


class SandboxSensorEntity(SandboxProxyEntity, SensorEntity):
    """Proxy for a sensor entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy sensor entity."""
        super().__init__(description, manager)
        if description.state_class:
            from homeassistant.components.sensor import SensorStateClass

            self._attr_state_class = SensorStateClass(description.state_class)
        unit = description.capabilities.get("native_unit_of_measurement")
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        return self._state_cache.get("state")


class SandboxSwitchEntity(SandboxProxyEntity, SwitchEntity):
    """Proxy for a switch entity in a sandbox."""

    @property
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)


class SandboxSceneEntity(SandboxProxyEntity, Scene):
    """Proxy for a scene entity in a sandbox."""

    async def async_activate(self, **kwargs: Any) -> None:
        """Forward activate to sandbox."""
        await self._forward_method("async_activate", **kwargs)


class SandboxEventEntity(SandboxProxyEntity, EventEntity):
    """Proxy for an event entity in a sandbox."""

    _unrecorded_attributes = frozenset({})

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy event entity."""
        super().__init__(description, manager)
        self._attr_event_types = description.capabilities.get("event_types", [])

    @callback
    def sandbox_update_state(self, state: str, attributes: dict[str, Any]) -> None:
        """Handle event firing from sandbox."""
        event_type = attributes.get("event_type")
        if event_type:
            event_attributes = {
                k: v
                for k, v in attributes.items()
                if k not in ("event_type", "state")
            }
            self._trigger_event(event_type, event_attributes or None)
            self.async_write_ha_state()
        else:
            super().sandbox_update_state(state, attributes)


class SandboxButtonEntity(SandboxProxyEntity, ButtonEntity):
    """Proxy for a button entity in a sandbox."""

    async def async_press(self) -> None:
        """Forward press to sandbox."""
        await self._forward_method("async_press")


class SandboxLockEntity(SandboxProxyEntity, LockEntity):
    """Proxy for a lock entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy lock entity."""
        super().__init__(description, manager)
        self._attr_supported_features = LockEntityFeature(
            description.supported_features
        )

    @property
    def is_locked(self) -> bool | None:
        """Return if the lock is locked."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "locked"

    @property
    def is_locking(self) -> bool | None:
        """Return if the lock is locking."""
        return self._state_cache.get("is_locking")

    @property
    def is_unlocking(self) -> bool | None:
        """Return if the lock is unlocking."""
        return self._state_cache.get("is_unlocking")

    @property
    def is_jammed(self) -> bool | None:
        """Return if the lock is jammed."""
        return self._state_cache.get("is_jammed")

    @property
    def is_open(self) -> bool | None:
        """Return if the lock is open."""
        return self._state_cache.get("is_open")

    async def async_lock(self, **kwargs: Any) -> None:
        """Forward lock to sandbox."""
        await self._forward_method("async_lock", **kwargs)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Forward unlock to sandbox."""
        await self._forward_method("async_unlock", **kwargs)

    async def async_open(self, **kwargs: Any) -> None:
        """Forward open to sandbox."""
        await self._forward_method("async_open", **kwargs)


class SandboxCoverEntity(SandboxProxyEntity, CoverEntity):
    """Proxy for a cover entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy cover entity."""
        super().__init__(description, manager)
        self._attr_supported_features = CoverEntityFeature(
            description.supported_features
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "closed"

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        return self._state_cache.get("is_opening")

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        return self._state_cache.get("is_closing")

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        return self._state_cache.get("current_cover_position")

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position."""
        return self._state_cache.get("current_cover_tilt_position")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Forward open_cover to sandbox."""
        await self._forward_method("async_open_cover", **kwargs)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Forward close_cover to sandbox."""
        await self._forward_method("async_close_cover", **kwargs)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Forward stop_cover to sandbox."""
        await self._forward_method("async_stop_cover", **kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Forward set_cover_position to sandbox."""
        await self._forward_method("async_set_cover_position", **kwargs)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Forward open_cover_tilt to sandbox."""
        await self._forward_method("async_open_cover_tilt", **kwargs)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Forward close_cover_tilt to sandbox."""
        await self._forward_method("async_close_cover_tilt", **kwargs)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Forward stop_cover_tilt to sandbox."""
        await self._forward_method("async_stop_cover_tilt", **kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Forward set_cover_tilt_position to sandbox."""
        await self._forward_method("async_set_cover_tilt_position", **kwargs)


class SandboxFanEntity(SandboxProxyEntity, FanEntity):
    """Proxy for a fan entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy fan entity."""
        super().__init__(description, manager)
        self._attr_supported_features = FanEntityFeature(
            description.supported_features
        )
        if preset_modes := description.capabilities.get("preset_modes"):
            self._attr_preset_modes = preset_modes
        if speed_count := description.capabilities.get("speed_count"):
            self._attr_speed_count = speed_count

    @property
    def is_on(self) -> bool | None:
        """Return if the fan is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._state_cache.get("percentage")

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._state_cache.get("preset_mode")

    @property
    def current_direction(self) -> str | None:
        """Return the current direction."""
        return self._state_cache.get("current_direction")

    @property
    def oscillating(self) -> bool | None:
        """Return if the fan is oscillating."""
        return self._state_cache.get("oscillating")

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", percentage=percentage, preset_mode=preset_mode, **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_set_percentage(self, percentage: int) -> None:
        """Forward set_percentage to sandbox."""
        await self._forward_method("async_set_percentage", percentage=percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode to sandbox."""
        await self._forward_method("async_set_preset_mode", preset_mode=preset_mode)

    async def async_set_direction(self, direction: str) -> None:
        """Forward set_direction to sandbox."""
        await self._forward_method("async_set_direction", direction=direction)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Forward oscillate to sandbox."""
        await self._forward_method("async_oscillate", oscillating=oscillating)


class SandboxClimateEntity(SandboxProxyEntity, ClimateEntity):
    """Proxy for a climate entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy climate entity."""
        super().__init__(description, manager)
        self._attr_supported_features = ClimateEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if hvac_modes := caps.get("hvac_modes"):
            self._attr_hvac_modes = [HVACMode(m) for m in hvac_modes]
        if fan_modes := caps.get("fan_modes"):
            self._attr_fan_modes = fan_modes
        if preset_modes := caps.get("preset_modes"):
            self._attr_preset_modes = preset_modes
        if swing_modes := caps.get("swing_modes"):
            self._attr_swing_modes = swing_modes
        if (min_temp := caps.get("min_temp")) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := caps.get("max_temp")) is not None:
            self._attr_max_temp = max_temp
        if (min_humidity := caps.get("min_humidity")) is not None:
            self._attr_min_humidity = min_humidity
        if (max_humidity := caps.get("max_humidity")) is not None:
            self._attr_max_humidity = max_humidity
        if (temp_step := caps.get("target_temperature_step")) is not None:
            self._attr_target_temperature_step = temp_step
        if temp_unit := caps.get("temperature_unit"):
            self._attr_temperature_unit = temp_unit

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        mode = self._state_cache.get("hvac_mode")
        if mode is None:
            return None
        return HVACMode(mode)

    @property
    def hvac_action(self) -> str | None:
        """Return the current HVAC action."""
        return self._state_cache.get("hvac_action")

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state_cache.get("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._state_cache.get("target_temperature")

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature."""
        return self._state_cache.get("target_temperature_high")

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature."""
        return self._state_cache.get("target_temperature_low")

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._state_cache.get("current_humidity")

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self._state_cache.get("target_humidity")

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self._state_cache.get("fan_mode")

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._state_cache.get("preset_mode")

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._state_cache.get("swing_mode")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature to sandbox."""
        await self._forward_method("async_set_temperature", **kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity to sandbox."""
        await self._forward_method("async_set_humidity", humidity=humidity)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Forward set_fan_mode to sandbox."""
        await self._forward_method("async_set_fan_mode", fan_mode=fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward set_hvac_mode to sandbox."""
        await self._forward_method("async_set_hvac_mode", hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode to sandbox."""
        await self._forward_method("async_set_preset_mode", preset_mode=preset_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Forward set_swing_mode to sandbox."""
        await self._forward_method("async_set_swing_mode", swing_mode=swing_mode)

    async def async_turn_on(self) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on")

    async def async_turn_off(self) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off")


class SandboxNumberEntity(SandboxProxyEntity, NumberEntity):
    """Proxy for a number entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy number entity."""
        super().__init__(description, manager)
        caps = description.capabilities
        if (min_val := caps.get("native_min_value")) is not None:
            self._attr_native_min_value = min_val
        if (max_val := caps.get("native_max_value")) is not None:
            self._attr_native_max_value = max_val
        if (step := caps.get("native_step")) is not None:
            self._attr_native_step = step
        if unit := caps.get("native_unit_of_measurement"):
            self._attr_native_unit_of_measurement = unit
        if mode := caps.get("mode"):
            self._attr_mode = NumberMode(mode)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        val = self._state_cache.get("state")
        if val is None:
            return None
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        """Forward set_native_value to sandbox."""
        await self._forward_method("async_set_native_value", value=value)


class SandboxSelectEntity(SandboxProxyEntity, SelectEntity):
    """Proxy for a select entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy select entity."""
        super().__init__(description, manager)
        self._attr_options = description.capabilities.get("options", [])

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._state_cache.get("state")

    async def async_select_option(self, option: str) -> None:
        """Forward select_option to sandbox."""
        await self._forward_method("async_select_option", option=option)


class SandboxTextEntity(SandboxProxyEntity, TextEntity):
    """Proxy for a text entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy text entity."""
        super().__init__(description, manager)
        caps = description.capabilities
        if (native_min := caps.get("native_min")) is not None:
            self._attr_native_min = native_min
        if (native_max := caps.get("native_max")) is not None:
            self._attr_native_max = native_max
        if mode := caps.get("mode"):
            self._attr_mode = TextMode(mode)
        if pattern := caps.get("pattern"):
            self._attr_pattern = pattern

    @property
    def native_value(self) -> str | None:
        """Return the current value."""
        return self._state_cache.get("state")

    async def async_set_value(self, value: str) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value)


class SandboxDateEntity(SandboxProxyEntity, DateEntity):
    """Proxy for a date entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current date value."""
        from datetime import date

        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            return date.fromisoformat(val)
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())


class SandboxDateTimeEntity(SandboxProxyEntity, DateTimeEntity):
    """Proxy for a datetime entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current datetime value."""
        from datetime import datetime, timezone

        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())


class SandboxTimeEntity(SandboxProxyEntity, TimeEntity):
    """Proxy for a time entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current time value."""
        from datetime import time

        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            return time.fromisoformat(val)
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())


class SandboxHumidifierEntity(SandboxProxyEntity, HumidifierEntity):
    """Proxy for a humidifier entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy humidifier entity."""
        super().__init__(description, manager)
        self._attr_supported_features = HumidifierEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if available_modes := caps.get("available_modes"):
            self._attr_available_modes = available_modes
        if (min_humidity := caps.get("min_humidity")) is not None:
            self._attr_min_humidity = min_humidity
        if (max_humidity := caps.get("max_humidity")) is not None:
            self._attr_max_humidity = max_humidity

    @property
    def is_on(self) -> bool | None:
        """Return if the humidifier is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._state_cache.get("current_humidity")

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self._state_cache.get("target_humidity")

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self._state_cache.get("mode")

    @property
    def action(self) -> str | None:
        """Return the current action."""
        return self._state_cache.get("action")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity to sandbox."""
        await self._forward_method("async_set_humidity", humidity=humidity)

    async def async_set_mode(self, mode: str) -> None:
        """Forward set_mode to sandbox."""
        await self._forward_method("async_set_mode", mode=mode)


class SandboxWaterHeaterEntity(SandboxProxyEntity, WaterHeaterEntity):
    """Proxy for a water_heater entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy water heater entity."""
        super().__init__(description, manager)
        self._attr_supported_features = WaterHeaterEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if operation_list := caps.get("operation_list"):
            self._attr_operation_list = operation_list
        if (min_temp := caps.get("min_temp")) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := caps.get("max_temp")) is not None:
            self._attr_max_temp = max_temp
        if temp_unit := caps.get("temperature_unit"):
            self._attr_temperature_unit = temp_unit

    @property
    def current_operation(self) -> str | None:
        """Return the current operation."""
        return self._state_cache.get("current_operation")

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state_cache.get("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._state_cache.get("target_temperature")

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return if away mode is on."""
        return self._state_cache.get("is_away_mode_on")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature to sandbox."""
        await self._forward_method("async_set_temperature", **kwargs)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Forward set_operation_mode to sandbox."""
        await self._forward_method("async_set_operation_mode", operation_mode=operation_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)


class SandboxVacuumEntity(SandboxProxyEntity, StateVacuumEntity):
    """Proxy for a vacuum entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy vacuum entity."""
        super().__init__(description, manager)
        self._attr_supported_features = VacuumEntityFeature(
            description.supported_features
        )
        if fan_speed_list := description.capabilities.get("fan_speed_list"):
            self._attr_fan_speed_list = fan_speed_list

    @property
    def activity(self) -> str | None:
        """Return the current vacuum activity."""
        return self._state_cache.get("activity")

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        return self._state_cache.get("battery_level")

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        return self._state_cache.get("fan_speed")

    async def async_start(self) -> None:
        """Forward start to sandbox."""
        await self._forward_method("async_start")

    async def async_pause(self) -> None:
        """Forward pause to sandbox."""
        await self._forward_method("async_pause")

    async def async_stop(self, **kwargs: Any) -> None:
        """Forward stop to sandbox."""
        await self._forward_method("async_stop", **kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Forward return_to_base to sandbox."""
        await self._forward_method("async_return_to_base", **kwargs)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Forward clean_spot to sandbox."""
        await self._forward_method("async_clean_spot", **kwargs)

    async def async_locate(self, **kwargs: Any) -> None:
        """Forward locate to sandbox."""
        await self._forward_method("async_locate", **kwargs)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Forward set_fan_speed to sandbox."""
        await self._forward_method("async_set_fan_speed", fan_speed=fan_speed, **kwargs)

    async def async_send_command(self, command: str, params: dict[str, Any] | list[Any] | None = None, **kwargs: Any) -> None:
        """Forward send_command to sandbox."""
        await self._forward_method("async_send_command", command=command, params=params, **kwargs)


class SandboxLawnMowerEntity(SandboxProxyEntity, LawnMowerEntity):
    """Proxy for a lawn_mower entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy lawn mower entity."""
        super().__init__(description, manager)
        self._attr_supported_features = LawnMowerEntityFeature(
            description.supported_features
        )

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current activity."""
        val = self._state_cache.get("activity")
        if val is None:
            return None
        return LawnMowerActivity(val)

    async def async_start_mowing(self) -> None:
        """Forward start_mowing to sandbox."""
        await self._forward_method("async_start_mowing")

    async def async_dock(self) -> None:
        """Forward dock to sandbox."""
        await self._forward_method("async_dock")

    async def async_pause(self) -> None:
        """Forward pause to sandbox."""
        await self._forward_method("async_pause")


class SandboxSirenEntity(SandboxProxyEntity, SirenEntity):
    """Proxy for a siren entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy siren entity."""
        super().__init__(description, manager)
        self._attr_supported_features = SirenEntityFeature(
            description.supported_features
        )
        if available_tones := description.capabilities.get("available_tones"):
            self._attr_available_tones = available_tones

    @property
    def is_on(self) -> bool | None:
        """Return if the siren is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)


class SandboxValveEntity(SandboxProxyEntity, ValveEntity):
    """Proxy for a valve entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy valve entity."""
        super().__init__(description, manager)
        self._attr_supported_features = ValveEntityFeature(
            description.supported_features
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "closed"

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening."""
        return self._state_cache.get("is_opening")

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing."""
        return self._state_cache.get("is_closing")

    @property
    def current_valve_position(self) -> int | None:
        """Return the current valve position."""
        return self._state_cache.get("current_valve_position")

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Forward open_valve to sandbox."""
        await self._forward_method("async_open_valve", **kwargs)

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Forward close_valve to sandbox."""
        await self._forward_method("async_close_valve", **kwargs)

    async def async_stop_valve(self, **kwargs: Any) -> None:
        """Forward stop_valve to sandbox."""
        await self._forward_method("async_stop_valve", **kwargs)

    async def async_set_valve_position(self, position: int) -> None:
        """Forward set_valve_position to sandbox."""
        await self._forward_method("async_set_valve_position", position=position)


class SandboxRemoteEntity(SandboxProxyEntity, RemoteEntity):
    """Proxy for a remote entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy remote entity."""
        super().__init__(description, manager)
        self._attr_supported_features = RemoteEntityFeature(
            description.supported_features
        )
        if activity_list := description.capabilities.get("activity_list"):
            self._attr_activity_list = activity_list

    @property
    def is_on(self) -> bool | None:
        """Return if the remote is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def current_activity(self) -> str | None:
        """Return the current activity."""
        return self._state_cache.get("current_activity")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_send_command(self, command: list[str], **kwargs: Any) -> None:
        """Forward send_command to sandbox."""
        await self._forward_method("async_send_command", command=command, **kwargs)


class SandboxMediaPlayerEntity(SandboxProxyEntity, MediaPlayerEntity):
    """Proxy for a media_player entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy media player entity."""
        super().__init__(description, manager)
        self._attr_supported_features = MediaPlayerEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if source_list := caps.get("source_list"):
            self._attr_source_list = source_list
        if sound_mode_list := caps.get("sound_mode_list"):
            self._attr_sound_mode_list = sound_mode_list

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return MediaPlayerState(state)

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        return self._state_cache.get("volume_level")

    @property
    def is_volume_muted(self) -> bool | None:
        """Return if volume is muted."""
        return self._state_cache.get("is_volume_muted")

    @property
    def media_content_id(self) -> str | None:
        """Return the media content ID."""
        return self._state_cache.get("media_content_id")

    @property
    def media_content_type(self) -> str | None:
        """Return the media content type."""
        return self._state_cache.get("media_content_type")

    @property
    def media_title(self) -> str | None:
        """Return the media title."""
        return self._state_cache.get("media_title")

    @property
    def media_artist(self) -> str | None:
        """Return the media artist."""
        return self._state_cache.get("media_artist")

    @property
    def media_album_name(self) -> str | None:
        """Return the media album name."""
        return self._state_cache.get("media_album_name")

    @property
    def media_duration(self) -> float | None:
        """Return the media duration."""
        return self._state_cache.get("media_duration")

    @property
    def media_position(self) -> float | None:
        """Return the media position."""
        return self._state_cache.get("media_position")

    @property
    def source(self) -> str | None:
        """Return the current source."""
        return self._state_cache.get("source")

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._state_cache.get("sound_mode")

    @property
    def shuffle(self) -> bool | None:
        """Return if shuffle is enabled."""
        return self._state_cache.get("shuffle")

    @property
    def repeat(self) -> RepeatMode | None:
        """Return the current repeat mode."""
        val = self._state_cache.get("repeat")
        if val is None:
            return None
        return RepeatMode(val)

    async def async_turn_on(self) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on")

    async def async_turn_off(self) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off")

    async def async_volume_up(self) -> None:
        """Forward volume_up to sandbox."""
        await self._forward_method("async_volume_up")

    async def async_volume_down(self) -> None:
        """Forward volume_down to sandbox."""
        await self._forward_method("async_volume_down")

    async def async_set_volume_level(self, volume: float) -> None:
        """Forward set_volume_level to sandbox."""
        await self._forward_method("async_set_volume_level", volume=volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Forward mute_volume to sandbox."""
        await self._forward_method("async_mute_volume", mute=mute)

    async def async_media_play(self) -> None:
        """Forward media_play to sandbox."""
        await self._forward_method("async_media_play")

    async def async_media_pause(self) -> None:
        """Forward media_pause to sandbox."""
        await self._forward_method("async_media_pause")

    async def async_media_stop(self) -> None:
        """Forward media_stop to sandbox."""
        await self._forward_method("async_media_stop")

    async def async_media_next_track(self) -> None:
        """Forward media_next_track to sandbox."""
        await self._forward_method("async_media_next_track")

    async def async_media_previous_track(self) -> None:
        """Forward media_previous_track to sandbox."""
        await self._forward_method("async_media_previous_track")

    async def async_media_seek(self, position: float) -> None:
        """Forward media_seek to sandbox."""
        await self._forward_method("async_media_seek", position=position)

    async def async_select_source(self, source: str) -> None:
        """Forward select_source to sandbox."""
        await self._forward_method("async_select_source", source=source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Forward select_sound_mode to sandbox."""
        await self._forward_method("async_select_sound_mode", sound_mode=sound_mode)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Forward play_media to sandbox."""
        await self._forward_method("async_play_media", media_type=media_type, media_id=media_id, **kwargs)


class SandboxWeatherEntity(SandboxProxyEntity, WeatherEntity):
    """Proxy for a weather entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy weather entity."""
        super().__init__(description, manager)
        self._attr_supported_features = WeatherEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if temp_unit := caps.get("native_temperature_unit"):
            self._attr_native_temperature_unit = temp_unit
        if pressure_unit := caps.get("native_pressure_unit"):
            self._attr_native_pressure_unit = pressure_unit
        if wind_speed_unit := caps.get("native_wind_speed_unit"):
            self._attr_native_wind_speed_unit = wind_speed_unit
        if visibility_unit := caps.get("native_visibility_unit"):
            self._attr_native_visibility_unit = visibility_unit
        if precipitation_unit := caps.get("native_precipitation_unit"):
            self._attr_native_precipitation_unit = precipitation_unit

    @property
    def condition(self) -> str | None:
        """Return the weather condition."""
        return self._state_cache.get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self._state_cache.get("native_temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self._state_cache.get("native_apparent_temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self._state_cache.get("native_pressure")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._state_cache.get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._state_cache.get("native_wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._state_cache.get("wind_bearing")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self._state_cache.get("native_visibility")

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Forward forecast_daily to sandbox."""
        return await self._forward_method("async_forecast_daily")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Forward forecast_hourly to sandbox."""
        return await self._forward_method("async_forecast_hourly")

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Forward forecast_twice_daily to sandbox."""
        return await self._forward_method("async_forecast_twice_daily")


class SandboxUpdateEntity(SandboxProxyEntity, UpdateEntity):
    """Proxy for an update entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy update entity."""
        super().__init__(description, manager)
        self._attr_supported_features = UpdateEntityFeature(
            description.supported_features
        )

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self._state_cache.get("installed_version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self._state_cache.get("latest_version")

    @property
    def title(self) -> str | None:
        """Return the title."""
        return self._state_cache.get("title")

    @property
    def release_summary(self) -> str | None:
        """Return the release summary."""
        return self._state_cache.get("release_summary")

    @property
    def release_url(self) -> str | None:
        """Return the release URL."""
        return self._state_cache.get("release_url")

    @property
    def in_progress(self) -> bool | int | None:
        """Return if update is in progress."""
        return self._state_cache.get("in_progress")

    @property
    def auto_update(self) -> bool:
        """Return if auto-update is enabled."""
        return self._state_cache.get("auto_update", False)

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Forward install to sandbox."""
        await self._forward_method("async_install", version=version, backup=backup, **kwargs)


class SandboxNotifyEntity(SandboxProxyEntity, NotifyEntity):
    """Proxy for a notify entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy notify entity."""
        super().__init__(description, manager)
        self._attr_supported_features = NotifyEntityFeature(
            description.supported_features
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Forward send_message to sandbox."""
        await self._forward_method("async_send_message", message=message, title=title)


class SandboxAlarmControlPanelEntity(SandboxProxyEntity, AlarmControlPanelEntity):
    """Proxy for an alarm_control_panel entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy alarm control panel entity."""
        super().__init__(description, manager)
        self._attr_supported_features = AlarmControlPanelEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if code_format := caps.get("code_format"):
            self._attr_code_format = code_format
        if (code_arm_required := caps.get("code_arm_required")) is not None:
            self._attr_code_arm_required = code_arm_required

    @property
    def alarm_state(self) -> str | None:
        """Return the alarm state."""
        return self._state_cache.get("state")

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Forward alarm_disarm to sandbox."""
        await self._forward_method("async_alarm_disarm", code=code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Forward alarm_arm_home to sandbox."""
        await self._forward_method("async_alarm_arm_home", code=code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Forward alarm_arm_away to sandbox."""
        await self._forward_method("async_alarm_arm_away", code=code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Forward alarm_arm_night to sandbox."""
        await self._forward_method("async_alarm_arm_night", code=code)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Forward alarm_arm_vacation to sandbox."""
        await self._forward_method("async_alarm_arm_vacation", code=code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Forward alarm_trigger to sandbox."""
        await self._forward_method("async_alarm_trigger", code=code)


class SandboxCalendarEntity(SandboxProxyEntity, CalendarEntity):
    """Proxy for a calendar entity in a sandbox."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event."""
        event_data = self._state_cache.get("event")
        if event_data is None:
            return None
        from datetime import date, datetime

        start = event_data.get("start")
        end = event_data.get("end")
        if isinstance(start, str):
            start = datetime.fromisoformat(start) if "T" in start else date.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end) if "T" in end else date.fromisoformat(end)
        return CalendarEvent(
            start=start,
            end=end,
            summary=event_data.get("summary", ""),
            description=event_data.get("description"),
            location=event_data.get("location"),
        )

    async def async_get_events(self, hass: HomeAssistant, start_date, end_date) -> list[CalendarEvent]:
        """Forward get_events to sandbox."""
        result = await self._forward_method(
            "async_get_events",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        if not result:
            return []
        from datetime import date, datetime

        events = []
        for ev in result:
            start = ev.get("start")
            end = ev.get("end")
            if isinstance(start, str):
                start = datetime.fromisoformat(start) if "T" in start else date.fromisoformat(start)
            if isinstance(end, str):
                end = datetime.fromisoformat(end) if "T" in end else date.fromisoformat(end)
            events.append(CalendarEvent(
                start=start,
                end=end,
                summary=ev.get("summary", ""),
                description=ev.get("description"),
                location=ev.get("location"),
            ))
        return events


_DOMAIN_ENTITY_MAP: dict[str, type[SandboxProxyEntity]] = {
    "alarm_control_panel": SandboxAlarmControlPanelEntity,
    "binary_sensor": SandboxBinarySensorEntity,
    "button": SandboxButtonEntity,
    "calendar": SandboxCalendarEntity,
    "climate": SandboxClimateEntity,
    "cover": SandboxCoverEntity,
    "date": SandboxDateEntity,
    "datetime": SandboxDateTimeEntity,
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
