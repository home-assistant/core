"""Component providing HA sensor support for Ring Door Bell/Chimes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import RingEntityMixin


@dataclass
class RingRequiredKeysMixin:
    """Mixin for required keys."""

    category: list[str]


@dataclass
class RingBinarySensorEntityDescription(
    BinarySensorEntityDescription, RingRequiredKeysMixin
):
    """Describes Ring binary sensor entity."""


BINARY_SENSOR_TYPES: tuple[RingBinarySensorEntityDescription, ...] = (
    RingBinarySensorEntityDescription(
        key="ding",
        translation_key="ding",
        category=["doorbots", "authorized_doorbots"],
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    RingBinarySensorEntityDescription(
        key="motion",
        category=["doorbots", "authorized_doorbots", "stickup_cams"],
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ring binary sensors from a config entry."""
    ring = hass.data[DOMAIN][config_entry.entry_id]["api"]
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    entities = [
        RingBinarySensor(config_entry.entry_id, ring, device, description)
        for device_type in ("doorbots", "authorized_doorbots", "stickup_cams")
        for description in BINARY_SENSOR_TYPES
        if device_type in description.category
        for device in devices[device_type]
    ]

    async_add_entities(entities)


class RingBinarySensor(RingEntityMixin, BinarySensorEntity):
    """A binary sensor implementation for Ring device."""

    _active_alert: dict[str, Any] | None = None
    entity_description: RingBinarySensorEntityDescription

    def __init__(
        self,
        config_entry_id,
        ring,
        device,
        description: RingBinarySensorEntityDescription,
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(config_entry_id, device)
        self.entity_description = description
        self._ring = ring
        self._attr_unique_id = f"{device.id}-{description.key}"
        self._update_alert()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.ring_objects["dings_data"].async_add_listener(self._dings_update_callback)
        self._dings_update_callback()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect callbacks."""
        await super().async_will_remove_from_hass()
        self.ring_objects["dings_data"].async_remove_listener(
            self._dings_update_callback
        )

    @callback
    def _dings_update_callback(self):
        """Call update method."""
        self._update_alert()
        self.async_write_ha_state()

    @callback
    def _update_alert(self):
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
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._active_alert is not None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        if self._active_alert is None:
            return attrs

        attrs["state"] = self._active_alert["state"]
        attrs["expires_at"] = datetime.fromtimestamp(
            self._active_alert.get("now") + self._active_alert.get("expires_in")
        ).isoformat()

        return attrs
