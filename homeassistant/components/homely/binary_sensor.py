"""Sensors provided by Homely."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from homelypy.devices import Device, MotionSensorMini, SmokeAlarm, WindowSensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import HomelyHomeCoordinator
from .homely_device import HomelyDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors based on a config entry."""
    homely_home: HomelyHomeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for homely_device in homely_home.devices.values():
        if isinstance(homely_device.homely_api_device, WindowSensor):
            entities.append(
                HomelyBinarySensorEntity(
                    homely_home, homely_device, WINDOW_SENSOR_DESCRIPTION
                )
            )
        elif isinstance(homely_device.homely_api_device, SmokeAlarm):
            entities.append(
                HomelyBinarySensorEntity(
                    homely_home, homely_device, SMOKE_ALARM_DESCRIPTION
                )
            )
        elif isinstance(homely_device.homely_api_device, MotionSensorMini):
            entities.append(
                HomelyBinarySensorEntity(
                    homely_home, homely_device, MOTION_SENSOR_DESCRIPTION
                )
            )
        entities.append(
            HomelyBinarySensorEntity(
                homely_home, homely_device, BATTERY_SENSOR_DESCRIPTION
            )
        )
    async_add_entities(entities)


@dataclass
class HomelyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing a Homely sensor entity."""

    value_fn: Callable[[Device], bool] = lambda _: _


class HomelyBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Abstract binary sensor class."""

    _attr_has_entity_name = True
    entity_description: HomelyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        homely_device: HomelyDevice,
        description: HomelyBinarySensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.homely_device = homely_device
        self.entity_description = description
        self._homely_device_state: Device = self.get_homely_device_state()
        self._attr_device_info = homely_device.device_info
        self._attr_unique_id = f"{homely_device.homely_api_device.id}_{self.name}"

    @property
    def is_on(self) -> bool:
        """Return the on state of the entity."""
        return self.entity_description.value_fn(self._homely_device_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._homely_device_state = self.get_homely_device_state()
        self.async_write_ha_state()

    def get_homely_device_state(self) -> Device:
        """Find my updated device."""
        return next(
            filter(
                lambda device: (device.id == self.homely_device.homely_api_device.id),
                self.coordinator.location.devices,
            )
        )


WINDOW_SENSOR_DESCRIPTION = HomelyBinarySensorEntityDescription(
    key="WindowSensorAlarm",
    name="Door/window",
    device_class=BinarySensorDeviceClass.WINDOW,
    value_fn=lambda device: device.alarm.alarm,
)

MOTION_SENSOR_DESCRIPTION = HomelyBinarySensorEntityDescription(
    key="MotionSensorAlarm",
    name="Motion",
    device_class=BinarySensorDeviceClass.MOTION,
    value_fn=lambda device: device.alarm.alarm,
)
SMOKE_ALARM_DESCRIPTION = HomelyBinarySensorEntityDescription(
    key="SmokeAlarmAlarm",
    name="Smoke",
    device_class=BinarySensorDeviceClass.SMOKE,
    value_fn=lambda device: device.alarm.fire,
)
BATTERY_SENSOR_DESCRIPTION = HomelyBinarySensorEntityDescription(
    key="BatteryLowAlarm",
    name="Battery low",
    device_class=BinarySensorDeviceClass.BATTERY,
    value_fn=lambda device: device.battery.low,
)
