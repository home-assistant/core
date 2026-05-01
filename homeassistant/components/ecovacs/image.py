"""Ecovacs image entities."""

from datetime import UTC, datetime
from typing import cast

from deebot_client.capabilities import Capabilities, CapabilityMap, DeviceType
from deebot_client.device import Device
from deebot_client.events.map import CachedMapInfoEvent, MapChangedEvent, MapTraceEvent
from deebot_client.map import Map

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsEntity

_TRACE_MAX_POINTS = 5000


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[ImageEntity] = [
        EcovacsMap(device, caps, hass)
        for device in controller.devices
        if (caps := device.capabilities.map)
    ]
    entities.extend(
        EcovacsMowerTraceMap(device, hass)
        for device in controller.devices
        if device.capabilities.device_type is DeviceType.MOWER
    )

    if entities:
        async_add_entities(entities)


class EcovacsMap(
    EcovacsEntity[CapabilityMap],
    ImageEntity,
):
    """Ecovacs map."""

    _attr_content_type = "image/svg+xml"

    def __init__(
        self,
        device: Device,
        capability: CapabilityMap,
        hass: HomeAssistant,
    ) -> None:
        """Initialize entity."""
        super().__init__(device, capability, hass=hass)
        self._attr_extra_state_attributes = {}
        self._map = cast(Map, self._device.map)

    entity_description = EntityDescription(
        key="map",
        translation_key="map",
    )

    def image(self) -> bytes | None:
        """Return bytes of image or None."""
        if svg := self._map.get_svg_map():
            return svg.encode()

        return None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_info(event: CachedMapInfoEvent) -> None:
            for map_obj in event.maps:
                if map_obj.using:
                    self._attr_extra_state_attributes["map_name"] = map_obj.name

        async def on_changed(event: MapChangedEvent) -> None:
            self._attr_image_last_updated = event.when
            self.async_write_ha_state()

        self._subscribe(self._capability.cached_info.event, on_info)
        self._subscribe(self._capability.changed.event, on_changed)

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await super().async_update()
        self._map.refresh()


class EcovacsMowerTraceMap(
    EcovacsEntity[Capabilities],
    ImageEntity,
):
    """Mower trajectory image rendered from MapTraceEvent."""

    _attr_content_type = "image/svg+xml"

    entity_description = EntityDescription(
        key="trace_map",
        translation_key="trace_map",
    )

    def __init__(self, device: Device, hass: HomeAssistant) -> None:
        """Initialize entity."""
        super().__init__(device, device.capabilities, hass=hass)
        self._points: list[tuple[int, int]] = []
        self._svg_cache: bytes | None = None

    def image(self) -> bytes | None:
        """Return bytes of image or None."""
        if not self._points:
            return None
        if self._svg_cache is None:
            self._svg_cache = self._render_svg().encode()
        return self._svg_cache

    def _render_svg(self) -> str:
        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        padding = max(50, (max(max_x - min_x, max_y - min_y)) // 20)
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding
        width = max_x - min_x
        height = max_y - min_y
        # Mower coordinates use bottom-up Y; flip for SVG top-down rendering.
        flipped = " ".join(f"{x},{max_y + min_y - y}" for x, y in self._points)
        stroke_width = max(20, width // 200)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{min_x} {min_y} {width} {height}" '
            f'preserveAspectRatio="xMidYMid meet">'
            f'<polyline points="{flipped}" fill="none" '
            f'stroke="#1976d2" stroke-width="{stroke_width}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f"</svg>"
        )

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_trace(event: MapTraceEvent) -> None:
            new_points: list[tuple[int, int]] = []
            for token in event.data.split(";"):
                token = token.strip()
                if not token:
                    continue
                try:
                    x_str, y_str = token.split(",")
                    new_points.append((int(x_str), int(y_str)))
                except ValueError:
                    continue
            if not new_points:
                return
            self._points.extend(new_points)
            if len(self._points) > _TRACE_MAX_POINTS:
                self._points = self._points[-_TRACE_MAX_POINTS:]
            self._svg_cache = None
            self._attr_image_last_updated = datetime.now(tz=UTC)
            self.async_write_ha_state()

        self._subscribe(MapTraceEvent, on_trace)
