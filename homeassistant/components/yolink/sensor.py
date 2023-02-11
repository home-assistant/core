"""YoLink Binary Sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.const import (
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DIMMER,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_SIREN,
    ATTR_DEVICE_SWITCH,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_THERMOSTAT,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_GARAGE_DOOR_CONTROLLER,
)
from yolink.device import YoLinkDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkSensorEntityDescriptionMixin:
    """Mixin for device type."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True


@dataclass
class YoLinkSensorEntityDescription(
    YoLinkSensorEntityDescriptionMixin, SensorEntityDescription
):
    """YoLink SensorEntityDescription."""

    value: Callable = lambda state: state
    should_update_entity: Callable = lambda state: True


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DIMMER,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_SIREN,
    ATTR_DEVICE_SWITCH,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_THERMOSTAT,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_GARAGE_DOOR_CONTROLLER,
]

BATTERY_POWER_SENSOR = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]

MCU_DEV_TEMPERATURE_SENSOR = [
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]


def cvt_battery(val: int | None) -> int | None:
    """Convert battery to percentage."""
    if val is None:
        return None
    if val > 0:
        return percentage.ordered_list_item_to_percentage([1, 2, 3, 4], val)
    return 0


SENSOR_TYPES: tuple[YoLinkSensorEntityDescription, ...] = (
    YoLinkSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        value=cvt_battery,
        exists_fn=lambda device: device.device_type in BATTERY_POWER_SENSOR,
    ),
    YoLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR],
    ),
    YoLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR],
    ),
    # mcu temperature
    YoLinkSensorEntityDescription(
        key="devTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in MCU_DEV_TEMPERATURE_SENSOR,
        should_update_entity=lambda value: value is not None,
    ),
    YoLinkSensorEntityDescription(
        key="loraInfo",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        name="Signal",
        value=lambda value: value["signal"] if value is not None else None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        should_update_entity=lambda value: value is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    sensor_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in SENSOR_DEVICE_TYPE
    ]
    entities = []
    for sensor_device_coordinator in sensor_device_coordinators:
        for description in SENSOR_TYPES:
            if description.exists_fn(sensor_device_coordinator.device):
                entities.append(
                    YoLinkSensorEntity(
                        config_entry,
                        sensor_device_coordinator,
                        description,
                    )
                )
    async_add_entities(entities)


class YoLinkSensorEntity(YoLinkEntity, SensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkSensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSensorEntityDescription,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )
        self._attr_name = (
            f"{coordinator.device.device_name} ({self.entity_description.name})"
        )

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        if (
            attr_val := self.entity_description.value(
                state.get(self.entity_description.key)
            )
        ) is None and self.entity_description.should_update_entity(attr_val) is False:
            return
        self._attr_native_value = attr_val
        self.async_write_ha_state()
