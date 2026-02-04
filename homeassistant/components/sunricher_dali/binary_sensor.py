"""Platform for Sunricher DALI binary sensor entities."""

from __future__ import annotations

from PySrDaliGateway import CallbackEventType, Device
from PySrDaliGateway.helper import is_motion_sensor
from PySrDaliGateway.types import MotionState, MotionStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_OCCUPANCY_ON_STATES = frozenset(
    {
        MotionState.MOTION,
        MotionState.OCCUPANCY,
        MotionState.PRESENCE,
    }
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunricher DALI binary sensor entities from config entry."""
    devices = entry.runtime_data.devices

    entities: list[BinarySensorEntity] = []
    for device in devices:
        if is_motion_sensor(device.dev_type):
            entities.append(SunricherDaliMotionSensor(device))
            entities.append(SunricherDaliOccupancySensor(device))

    if entities:
        async_add_entities(entities)


class SunricherDaliMotionSensor(DaliDeviceEntity, BinarySensorEntity):
    """Instantaneous motion detection sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, device: Device) -> None:
        """Initialize the motion sensor."""
        super().__init__(device)
        self._device = device
        self._attr_unique_id = f"{device.dev_id}_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.MOTION_STATUS, self._handle_motion_status
            )
        )

        self._device.read_status()

    @callback
    def _handle_motion_status(self, status: MotionStatus) -> None:
        """Handle motion status updates."""
        motion_state = status["motion_state"]
        if motion_state == MotionState.MOTION:
            self._attr_is_on = True
            self.schedule_update_ha_state()
        elif motion_state == MotionState.NO_MOTION:
            self._attr_is_on = False
            self.schedule_update_ha_state()


class SunricherDaliOccupancySensor(DaliDeviceEntity, BinarySensorEntity):
    """Persistent occupancy detection sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, device: Device) -> None:
        """Initialize the occupancy sensor."""
        super().__init__(device)
        self._device = device
        self._attr_unique_id = f"{device.dev_id}_occupancy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.MOTION_STATUS, self._handle_motion_status
            )
        )

        self._device.read_status()

    @callback
    def _handle_motion_status(self, status: MotionStatus) -> None:
        """Handle motion status updates."""
        motion_state = status["motion_state"]
        if motion_state in _OCCUPANCY_ON_STATES:
            self._attr_is_on = True
            self.schedule_update_ha_state()
        elif motion_state == MotionState.VACANT:
            self._attr_is_on = False
            self.schedule_update_ha_state()
