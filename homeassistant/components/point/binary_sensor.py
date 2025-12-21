"""Support for Minut Point binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from pypoint import EVENTS

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PointConfigEntry
from .const import SIGNAL_WEBHOOK
from .coordinator import PointDataUpdateCoordinator
from .entity import MinutPointEntity

_LOGGER = logging.getLogger(__name__)


DEVICES: dict[str, Any] = {
    "alarm": {"icon": "mdi:alarm-bell"},
    "battery": {"device_class": BinarySensorDeviceClass.BATTERY},
    "button_press": {"icon": "mdi:gesture-tap-button"},
    "cold": {"device_class": BinarySensorDeviceClass.COLD},
    "connectivity": {"device_class": BinarySensorDeviceClass.CONNECTIVITY},
    "dry": {"icon": "mdi:water"},
    "glass": {"icon": "mdi:window-closed-variant"},
    "heat": {"device_class": BinarySensorDeviceClass.HEAT},
    "moisture": {"device_class": BinarySensorDeviceClass.MOISTURE},
    "motion": {"device_class": BinarySensorDeviceClass.MOTION},
    "noise": {"icon": "mdi:volume-high"},
    "sound": {"device_class": BinarySensorDeviceClass.SOUND},
    "tamper_old": {"icon": "mdi:shield-alert"},
    "tamper": {"icon": "mdi:shield-alert"},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PointConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Point's binary sensors based on a config entry."""

    coordinator = config_entry.runtime_data

    def async_discover_sensor(device_id: str) -> None:
        """Discover and add a discovered sensor."""
        async_add_entities(
            MinutPointBinarySensor(coordinator, device_id, device_name)
            for device_name in DEVICES
            if device_name in EVENTS
        )

    coordinator.new_device_callbacks.append(async_discover_sensor)

    async_add_entities(
        MinutPointBinarySensor(coordinator, device_id, device_name)
        for device_name in DEVICES
        if device_name in EVENTS
        for device_id in coordinator.point.device_ids
    )


class MinutPointBinarySensor(MinutPointEntity, BinarySensorEntity):
    """The platform class required by Home Assistant."""

    def __init__(
        self, coordinator: PointDataUpdateCoordinator, device_id: str, key: str
    ) -> None:
        """Initialize the binary sensor."""
        self._attr_device_class = DEVICES[key].get("device_class", key)
        super().__init__(coordinator, device_id)
        self._device_name = key
        self._events = EVENTS[key]
        self._attr_unique_id = f"point.{device_id}-{key}"
        self._attr_icon = DEVICES[key].get("icon")

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_WEBHOOK, self._webhook_event)
        )

    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor."""
        if self.device_class == BinarySensorDeviceClass.CONNECTIVITY:
            # connectivity is the other way around.
            self._attr_is_on = self._events[0] not in self.device.ongoing_events
        else:
            self._attr_is_on = self._events[0] in self.device.ongoing_events
        super()._handle_coordinator_update()

    @callback
    def _webhook_event(self, data, webhook):
        """Process new event from the webhook."""
        if self.device.webhook != webhook:
            return
        _type = data.get("event", {}).get("type")
        _device_id = data.get("event", {}).get("device_id")
        if _type not in self._events or _device_id != self.device.device_id:
            return
        _LOGGER.debug("Received webhook: %s", _type)
        if _type == self._events[0]:
            _is_on = True
        elif _type == self._events[1]:
            _is_on = False
        else:
            return

        if self.device_class == BinarySensorDeviceClass.CONNECTIVITY:
            # connectivity is the other way around.
            self._attr_is_on = not _is_on
        else:
            self._attr_is_on = _is_on
        self.async_write_ha_state()
