"""Component providing HA sensor support for Ring Door Bell/Chimes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ring_doorbell import Ring, RingEvent, RingGeneric

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingConfigEntry
from .coordinator import RingNotificationsCoordinator
from .entity import RingBaseEntity


@dataclass(frozen=True, kw_only=True)
class RingBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Ring binary sensor entity."""

    exists_fn: Callable[[RingGeneric], bool]


BINARY_SENSOR_TYPES: tuple[RingBinarySensorEntityDescription, ...] = (
    RingBinarySensorEntityDescription(
        key="ding",
        translation_key="ding",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        exists_fn=lambda device: device.family
        in {"doorbots", "authorized_doorbots", "other"},
    ),
    RingBinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        exists_fn=lambda device: device.family
        in {"doorbots", "authorized_doorbots", "stickup_cams"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ring binary sensors from a config entry."""
    ring_data = entry.runtime_data

    entities = [
        RingBinarySensor(
            ring_data.api,
            device,
            ring_data.notifications_coordinator,
            description,
        )
        for description in BINARY_SENSOR_TYPES
        for device in ring_data.devices.all_devices
        if description.exists_fn(device)
    ]

    async_add_entities(entities)


class RingBinarySensor(
    RingBaseEntity[RingNotificationsCoordinator], BinarySensorEntity
):
    """A binary sensor implementation for Ring device."""

    _active_alert: RingEvent | None = None
    entity_description: RingBinarySensorEntityDescription

    def __init__(
        self,
        ring: Ring,
        device: RingGeneric,
        coordinator: RingNotificationsCoordinator,
        description: RingBinarySensorEntityDescription,
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(
            device,
            coordinator,
        )
        self.entity_description = description
        self._ring = ring
        self._attr_unique_id = f"{device.id}-{description.key}"
        self._update_alert()

    @callback
    def _handle_coordinator_update(self, _: Any = None) -> None:
        """Call update method."""
        self._update_alert()
        super()._handle_coordinator_update()

    @callback
    def _update_alert(self) -> None:
        """Update active alert."""
        self._active_alert = next(
            (
                alert
                for alert in self._ring.active_alerts()
                if alert["kind"] == self.entity_description.key
                and alert["doorbot_id"] == self._device.id
            ),
            None,
        )

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self._active_alert is not None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        if self._active_alert is None:
            return attrs

        assert isinstance(attrs, dict)
        attrs["state"] = self._active_alert["state"]
        now = self._active_alert.get("now")
        expires_in = self._active_alert.get("expires_in")
        assert now and expires_in
        attrs["expires_at"] = datetime.fromtimestamp(now + expires_in).isoformat()

        return attrs
