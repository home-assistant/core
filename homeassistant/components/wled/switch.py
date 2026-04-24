"""Support for WLED switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from wled import WLED

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DURATION, ATTR_TARGET_BRIGHTNESS, ATTR_UDP_PORT
from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class WLEDSegmentSwitchEntityDescription(SwitchEntityDescription):
    """Describes WLED segment switch entity."""

    segment_translation_key: str
    set_segment: Callable[[WLED, int, bool], Awaitable[None]]


SEGMENT_SWITCHES: tuple[WLEDSegmentSwitchEntityDescription, ...] = (
    WLEDSegmentSwitchEntityDescription(
        key="reverse",
        translation_key="reverse",
        segment_translation_key="segment_reverse",
        set_segment=lambda wled, segment, value: wled.segment(
            segment_id=segment,
            reverse=value,
        ),
    ),
    WLEDSegmentSwitchEntityDescription(
        key="freeze",
        translation_key="freeze",
        segment_translation_key="segment_freeze",
        set_segment=lambda wled, segment, value: wled.segment(
            segment_id=segment,
            freeze=value,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED switch based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            WLEDNightlightSwitch(coordinator),
            WLEDSyncSendSwitch(coordinator),
            WLEDSyncReceiveSwitch(coordinator),
        ]
    )

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )
    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDNightlightSwitch(WLEDEntity, SwitchEntity):
    """Defines a WLED nightlight switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "nightlight"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED nightlight switch."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_nightlight"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        state = self.coordinator.data.state
        return {
            ATTR_DURATION: state.nightlight.duration,
            ATTR_TARGET_BRIGHTNESS: state.nightlight.target_brightness,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.nightlight.on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED nightlight switch."""
        await self.coordinator.wled.nightlight(on=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED nightlight switch."""
        await self.coordinator.wled.nightlight(on=True)


class WLEDSyncSendSwitch(WLEDEntity, SwitchEntity):
    """Defines a WLED sync send switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "sync_send"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED sync send switch."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_sync_send"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {ATTR_UDP_PORT: self.coordinator.data.info.udp_port}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.sync.send)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED sync send switch."""
        await self.coordinator.wled.sync(send=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED sync send switch."""
        await self.coordinator.wled.sync(send=True)


class WLEDSyncReceiveSwitch(WLEDEntity, SwitchEntity):
    """Defines a WLED sync receive switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "sync_receive"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED sync receive switch."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_sync_receive"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {ATTR_UDP_PORT: self.coordinator.data.info.udp_port}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.sync.receive)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED sync receive switch."""
        await self.coordinator.wled.sync(receive=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED sync receive switch."""
        await self.coordinator.wled.sync(receive=True)


class WLEDSegmentSwitch(WLEDEntity, SwitchEntity):
    """Defines a WLED segment switch."""

    entity_description: WLEDSegmentSwitchEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        segment: int,
        description: WLEDSegmentSwitchEntityDescription,
    ) -> None:
        """Initialize WLED segment switch."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._segment = segment

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment != 0:
            self._attr_translation_key = description.segment_translation_key
            self._attr_translation_placeholders = {"segment": str(segment)}
        else:
            self._attr_translation_key = description.translation_key

        self._attr_unique_id = (
            f"{coordinator.data.info.mac_address}_{description.key}_{segment}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self._segment in self.coordinator.data.state.segments
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        segment = self.coordinator.data.state.segments[self._segment]
        return bool(getattr(segment, self.entity_description.key))

    async def _async_set_state(self, value: bool) -> None:
        """Set segment state."""
        await self.entity_description.set_segment(
            self.coordinator.wled,
            self._segment,
            value,
        )

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED segment switch."""
        await self._async_set_state(True)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED segment switch."""
        await self._async_set_state(False)


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {
        segment.segment_id
        for segment in coordinator.data.state.segments.values()
        if segment.segment_id is not None
    }

    new_entities: list[WLEDSegmentSwitch] = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.extend(
            WLEDSegmentSwitch(
                coordinator=coordinator,
                segment=segment_id,
                description=description,
            )
            for description in SEGMENT_SWITCHES
        )

    async_add_entities(new_entities)
