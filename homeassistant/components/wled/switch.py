"""Support for WLED switches."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WLEDConfigEntry
from .const import ATTR_DURATION, ATTR_FADE, ATTR_TARGET_BRIGHTNESS, ATTR_UDP_PORT
from .coordinator import WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
            ATTR_FADE: state.nightlight.fade,
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


class WLEDReverseSwitch(WLEDEntity, SwitchEntity):
    """Defines a WLED reverse effect switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reverse"
    _segment: int

    def __init__(self, coordinator: WLEDDataUpdateCoordinator, segment: int) -> None:
        """Initialize WLED reverse effect switch."""
        super().__init__(coordinator=coordinator)

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment != 0:
            self._attr_translation_key = "segment_reverse"
            self._attr_translation_placeholders = {"segment": str(segment)}

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_reverse_{segment}"
        self._segment = segment

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except IndexError:
            return False

        return super().available

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.coordinator.data.state.segments[self._segment].reverse

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED reverse effect switch."""
        await self.coordinator.wled.segment(segment_id=self._segment, reverse=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED reverse effect switch."""
        await self.coordinator.wled.segment(segment_id=self._segment, reverse=True)


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {segment.segment_id for segment in coordinator.data.state.segments}

    new_entities: list[WLEDReverseSwitch] = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.append(WLEDReverseSwitch(coordinator, segment_id))

    async_add_entities(new_entities)
