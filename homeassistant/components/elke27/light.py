"""Lights for Elke27 lights."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elke27DataUpdateCoordinator
from .entity import build_unique_id, device_info_for_entry, sanitize_name, unique_base

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .hub import Elke27Hub
    from .models import Elke27RuntimeData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
_ELK_MAX_DIM_LEVEL = 99


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 lights from a config entry."""
    data: Elke27RuntimeData | None = entry.runtime_data
    if data is None:
        _LOGGER.debug("Skipping light setup because runtime data is missing")
        return
    hub = data.hub
    coordinator = data.coordinator
    known_ids: set[int] = set()

    def _async_add_lights() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Light entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27Light] = []
        lights = list(_iter_lights(snapshot))
        if not lights:
            _LOGGER.debug("No lights available for entity creation")
            return
        for light in lights:
            light_id = getattr(light, "light_id", None)
            if not isinstance(light_id, int):
                continue
            if light_id in known_ids:
                continue
            known_ids.add(light_id)
            entities.append(Elke27Light(coordinator, hub, entry, light_id, light))
        if entities:
            async_add_entities(entities)

    _async_add_lights()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_lights))


class Elke27Light(CoordinatorEntity[Elke27DataUpdateCoordinator], LightEntity):
    """Representation of an Elke27 light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.BRIGHTNESS}
    _attr_has_entity_name = True
    _attr_translation_key = "light"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        light_id: int,
        light: Any,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._light_id = light_id
        self._attr_name = (
            sanitize_name(getattr(light, "name", None)) or f"Light {light_id}"
        )
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "light",
            light_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def is_on(self) -> bool | None:
        """Return if the light is on."""
        light = _get_light(self.coordinator.data, self._light_id)
        if light is None:
            self._log_missing()
            return None
        is_on = getattr(light, "on", None)
        if isinstance(is_on, bool):
            return is_on
        level = getattr(light, "level", None)
        if isinstance(level, int):
            return level > 0
        return None

    @property
    def brightness(self) -> int | None:
        """Return the current brightness value (0-255)."""
        light = _get_light(self.coordinator.data, self._light_id)
        if light is None:
            return None
        level = getattr(light, "level", None)
        if not isinstance(level, int):
            return None
        bounded = max(0, min(_ELK_MAX_DIM_LEVEL, level))
        return round(bounded * 255 / _ELK_MAX_DIM_LEVEL)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on if supported by the client."""
        try:
            if ATTR_BRIGHTNESS in kwargs:
                level = _level_from_kwargs(kwargs)
                await self._hub.async_set_light(
                    self._light_id, state=True, level=level
                )
            else:
                await self._hub.async_set_light(
                    self._light_id, state=True, level=_ELK_MAX_DIM_LEVEL
                )
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the light off if supported by the client."""
        try:
            await self._hub.async_set_light(self._light_id, state=False, level=0)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_light(self.coordinator.data, self._light_id) is not None
        )

    def _log_missing(self) -> None:
        """Log when the light snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Light %s missing from snapshot", self._light_id)


def _level_from_kwargs(kwargs: dict[str, Any]) -> int:
    """Map Home Assistant brightness kwargs to Elk level (0-100)."""
    brightness = kwargs.get(ATTR_BRIGHTNESS)
    if isinstance(brightness, int):
        bounded = max(0, min(255, brightness))
        # Keep minimum 1 for ON requests with brightness set.
        return max(1, round(bounded * _ELK_MAX_DIM_LEVEL / 255))
    return _ELK_MAX_DIM_LEVEL


def _iter_lights(snapshot: Any) -> Iterable[Any]:
    lights = getattr(snapshot, "lights", None)
    if lights is None:
        return []
    if isinstance(lights, Mapping):
        return list(lights.values())
    if isinstance(lights, list | tuple):
        return lights
    return []


def _get_light(snapshot: Any, light_id: int) -> Any | None:
    for light in _iter_lights(snapshot):
        if getattr(light, "light_id", None) == light_id:
            return light
    return None
