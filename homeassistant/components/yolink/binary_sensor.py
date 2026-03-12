"""YoLink BinarySensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.const import (
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR,
    ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER,
    ATTR_DEVICE_SMOKE_ALARM,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
)
from yolink.device import YoLinkDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEV_MODEL_WATER_METER_YS5018_EC,
    DEV_MODEL_WATER_METER_YS5018_UC,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True, kw_only=True)
class YoLinkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """YoLink BinarySensorEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    should_update_entity: Callable = lambda _: True
    value: Callable[[YoLinkDevice, dict], bool | None]
    is_available: Callable[[YoLinkDevice, dict], bool] = lambda _, __: True


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
    ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER,
    ATTR_DEVICE_SMOKE_ALARM,
]


def parse_data_leak_sensor_state(device: YoLinkDevice, data: dict) -> bool | None:
    """Parse leak sensor state."""
    if device.device_type == ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR:
        if (state := data.get("state")) is None or (
            value := state.get("waterDetection")
        ) is None:
            return None
        return (
            value == "normal"
            if data.get("waterDetectionMode") == "WaterPeak"
            else value == "leak"
        )
    return data.get("state") in ["alert", "full"]


def is_leak_sensor_state_available(device: YoLinkDevice, data: dict) -> bool:
    """Check leak sensor state availability."""
    if device.device_type == ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR:
        if (
            (alarms := data.get("alarm")) is not None
            and isinstance(alarms, list)
            and "Alert.DetectorError" in alarms
        ):
            return False
    if (alarms := data.get("alarmState")) is not None and alarms.get(
        "detectorError"
    ) is True:
        return False
    return True


SENSOR_TYPES: tuple[YoLinkBinarySensorEntityDescription, ...] = (
    YoLinkBinarySensorEntityDescription(
        key="door_state",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_DOOR_SENSOR,
        value=lambda device, data: (
            value == "open" if (value := data.get("state")) is not None else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="motion_state",
        device_class=BinarySensorDeviceClass.MOTION,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MOTION_SENSOR,
        value=lambda device, data: (
            value == "alert" if (value := data.get("state")) is not None else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="leak_state",
        device_class=BinarySensorDeviceClass.MOISTURE,
        exists_fn=lambda device: (
            device.device_type
            in [ATTR_DEVICE_LEAK_SENSOR, ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR]
        ),
        value=parse_data_leak_sensor_state,
        is_available=is_leak_sensor_state_available,
    ),
    YoLinkBinarySensorEntityDescription(
        key="vibration_state",
        device_class=BinarySensorDeviceClass.VIBRATION,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_VIBRATION_SENSOR,
        value=lambda device, data: (
            value == "alert" if (value := data.get("state")) is not None else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="co_detected",
        device_class=BinarySensorDeviceClass.CO,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_CO_SMOKE_SENSOR,
        value=lambda device, data: (
            state.get("gasAlarm") if (state := data.get("state")) is not None else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="smoke_detected",
        device_class=BinarySensorDeviceClass.SMOKE,
        exists_fn=lambda device: (
            device.device_type in [ATTR_DEVICE_CO_SMOKE_SENSOR, ATTR_DEVICE_SMOKE_ALARM]
        ),
        value=lambda device, data: (
            state.get("smokeAlarm") is True or state.get("denseSmokeAlarm") is True
            if (state := data.get("state")) is not None
            else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="pipe_leak_detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
        exists_fn=lambda device: (
            device.device_type
            in [
                ATTR_DEVICE_WATER_METER_CONTROLLER,
                ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER,
            ]
        ),
        # This property will be lost during valve operation.
        should_update_entity=lambda value: value is not None,
        value=lambda device, data: (
            alarms.get("leak") if (alarms := data.get("alarm")) is not None else None
        ),
    ),
    YoLinkBinarySensorEntityDescription(
        key="water_running",
        translation_key="water_running",
        exists_fn=lambda device: (
            device.device_type == ATTR_DEVICE_WATER_METER_CONTROLLER
            and device.device_model_name
            in [DEV_MODEL_WATER_METER_YS5018_EC, DEV_MODEL_WATER_METER_YS5018_UC]
        ),
        should_update_entity=lambda value: value is not None,
        value=lambda device, data: (
            state.get("waterFlowing")
            if (state := data.get("state")) is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    binary_sensor_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in SENSOR_DEVICE_TYPE
    ]
    async_add_entities(
        YoLinkBinarySensorEntity(
            config_entry, binary_sensor_device_coordinator, description
        )
        for binary_sensor_device_coordinator in binary_sensor_device_coordinators
        for description in SENSOR_TYPES
        if description.exists_fn(binary_sensor_device_coordinator.device)
    )


class YoLinkBinarySensorEntity(YoLinkEntity, BinarySensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkBinarySensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkBinarySensorEntityDescription,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        if (
            _attr_val := self.entity_description.value(self.coordinator.device, state)
        ) is None or self.entity_description.should_update_entity(_attr_val) is False:
            return
        _is_attr_available = self.entity_description.is_available(
            self.coordinator.device, state
        )
        self._attr_available = _is_attr_available
        self._attr_is_on = _attr_val if _is_attr_available else None
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true is device is available."""
        return super().available and self.coordinator.dev_online
