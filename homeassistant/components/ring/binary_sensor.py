"""Component providing HA sensor support for Ring Door Bell/Chimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ring_doorbell import RingCapability, RingEvent
from ring_doorbell.const import KIND_DING, KIND_MOTION

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_at

from . import RingConfigEntry
from .coordinator import RingListenCoordinator
from .entity import DeprecatedInfo, RingBaseEntity, RingDeviceT, RingEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RingBinarySensorEntityDescription(
    BinarySensorEntityDescription, RingEntityDescription[RingDeviceT]
):
    """Describes Ring binary sensor entity."""


BINARY_SENSOR_TYPES: tuple[RingBinarySensorEntityDescription, ...] = (
    RingBinarySensorEntityDescription(
        key=KIND_DING,
        translation_key=KIND_DING,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        exists_fn=lambda device: device.has_capability(RingCapability.DING),
        deprecated_info=DeprecatedInfo(
            new_platform=Platform.EVENT, breaks_in_ha_version="2025.4.0"
        ),
    ),
    RingBinarySensorEntityDescription(
        key=KIND_MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
        exists_fn=lambda device: device.has_capability(RingCapability.MOTION_DETECTION),
        deprecated_info=DeprecatedInfo(
            new_platform=Platform.EVENT, breaks_in_ha_version="2025.4.0"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ring binary sensors from a config entry."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator
    listen_coordinator = ring_data.listen_coordinator

    RingBinarySensor.process_devices(
        hass,
        lambda device, description: RingBinarySensor(
            device, listen_coordinator, description
        ),
        devices_coordinator,
        async_add_entities=async_add_entities,
        domain=BINARY_SENSOR_DOMAIN,
        descriptions=BINARY_SENSOR_TYPES,
    )


class RingBinarySensor(
    RingBaseEntity[RingListenCoordinator, RingDeviceT], BinarySensorEntity
):
    """A binary sensor implementation for Ring device."""

    _active_alert: RingEvent | None = None
    RingBinarySensorEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingListenCoordinator,
        description: RingBinarySensorEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a binary sensor for Ring device."""
        super().__init__(
            device,
            coordinator,
            description,
        )
        self._attr_is_on = False
        self._active_alert: RingEvent | None = None
        self._cancel_callback: CALLBACK_TYPE | None = None

    @callback
    def _async_handle_event(self, alert: RingEvent) -> None:
        """Handle the event."""
        self._attr_is_on = True
        self._active_alert = alert
        loop = self.hass.loop
        when = loop.time() + alert.expires_in
        if self._cancel_callback:
            self._cancel_callback()
        self._cancel_callback = async_call_at(self.hass, self._async_cancel_event, when)

    @callback
    def _async_cancel_event(self, _now: Any) -> None:
        """Clear the event."""
        self._cancel_callback = None
        self._attr_is_on = False
        self._active_alert = None
        self.async_write_ha_state()

    def _get_coordinator_alert(self) -> RingEvent | None:
        return self.coordinator.alerts.get(
            (self._device.device_api_id, self.entity_description.key)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        if alert := self._get_coordinator_alert():
            self._async_handle_event(alert)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.event_listener.started

    async def async_update(self) -> None:
        """All updates are passive."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        if self._active_alert is None:
            return attrs

        assert isinstance(attrs, dict)
        attrs["state"] = self._active_alert.state
        now = self._active_alert.now
        expires_in = self._active_alert.expires_in
        assert now and expires_in
        attrs["expires_at"] = datetime.fromtimestamp(now + expires_in).isoformat()

        return attrs
