"""YoLink Sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.const import (
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_DIMMER,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_FINGER,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_POWER_FAILURE_ALARM,
    ATTR_DEVICE_SIREN,
    ATTR_DEVICE_SMART_REMOTER,
    ATTR_DEVICE_SWITCH,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_THERMOSTAT,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_WATER_DEPTH_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
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
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from .const import (
    DEV_MODEL_PLUG_YS6602_EC,
    DEV_MODEL_PLUG_YS6602_UC,
    DEV_MODEL_PLUG_YS6803_EC,
    DEV_MODEL_PLUG_YS6803_UC,
    DEV_MODEL_TH_SENSOR_YS8004_EC,
    DEV_MODEL_TH_SENSOR_YS8004_UC,
    DEV_MODEL_TH_SENSOR_YS8014_EC,
    DEV_MODEL_TH_SENSOR_YS8014_UC,
    DEV_MODEL_TH_SENSOR_YS8017_EC,
    DEV_MODEL_TH_SENSOR_YS8017_UC,
    DOMAIN,
)
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True, kw_only=True)
class YoLinkSensorEntityDescription(SensorEntityDescription):
    """YoLink SensorEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    should_update_entity: Callable = lambda state: True
    value: Callable = lambda state: state


SENSOR_DEVICE_TYPE = [
    ATTR_DEVICE_DIMMER,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_FINGER,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_SMART_REMOTER,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_POWER_FAILURE_ALARM,
    ATTR_DEVICE_SIREN,
    ATTR_DEVICE_SWITCH,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_THERMOSTAT,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_WATER_DEPTH_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_GARAGE_DOOR_CONTROLLER,
]

BATTERY_POWER_SENSOR = [
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_FINGER,
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_POWER_FAILURE_ALARM,
    ATTR_DEVICE_SIREN,
    ATTR_DEVICE_SMART_REMOTER,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_VIBRATION_SENSOR,
    ATTR_DEVICE_LOCK,
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
    ATTR_DEVICE_WATER_DEPTH_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
]

MCU_DEV_TEMPERATURE_SENSOR = [
    ATTR_DEVICE_LEAK_SENSOR,
    ATTR_DEVICE_MOTION_SENSOR,
    ATTR_DEVICE_CO_SMOKE_SENSOR,
]

NONE_HUMIDITY_SENSOR_MODELS = [
    DEV_MODEL_TH_SENSOR_YS8004_EC,
    DEV_MODEL_TH_SENSOR_YS8004_UC,
    DEV_MODEL_TH_SENSOR_YS8014_EC,
    DEV_MODEL_TH_SENSOR_YS8014_UC,
    DEV_MODEL_TH_SENSOR_YS8017_UC,
    DEV_MODEL_TH_SENSOR_YS8017_EC,
]

POWER_SUPPORT_MODELS = [
    DEV_MODEL_PLUG_YS6602_UC,
    DEV_MODEL_PLUG_YS6602_EC,
    DEV_MODEL_PLUG_YS6803_UC,
    DEV_MODEL_PLUG_YS6803_EC,
]


def cvt_battery(val: int | None) -> int | None:
    """Convert battery to percentage."""
    if val is None:
        return None
    if val > 0:
        return percentage.ordered_list_item_to_percentage([1, 2, 3, 4], val)
    return 0


def cvt_volume(val: int | None) -> str | None:
    """Convert volume to string."""
    if val is None:
        return None
    volume_level = {1: "low", 2: "medium", 3: "high"}
    return volume_level.get(val)


SENSOR_TYPES: tuple[YoLinkSensorEntityDescription, ...] = (
    YoLinkSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=cvt_battery,
        exists_fn=lambda device: device.device_type in BATTERY_POWER_SENSOR,
        should_update_entity=lambda value: value is not None,
    ),
    YoLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR]
        and device.device_model_name not in NONE_HUMIDITY_SENSOR_MODELS,
    ),
    YoLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_TH_SENSOR],
    ),
    # mcu temperature
    YoLinkSensorEntityDescription(
        key="devTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda device: device.device_type in MCU_DEV_TEMPERATURE_SENSOR,
        should_update_entity=lambda value: value is not None,
    ),
    YoLinkSensorEntityDescription(
        key="loraInfo",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value=lambda value: value["signal"] if value is not None else None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        should_update_entity=lambda value: value is not None,
    ),
    YoLinkSensorEntityDescription(
        key="state",
        translation_key="power_failure_alarm",
        device_class=SensorDeviceClass.ENUM,
        options=["normal", "alert", "off"],
        exists_fn=lambda device: device.device_type in ATTR_DEVICE_POWER_FAILURE_ALARM,
    ),
    YoLinkSensorEntityDescription(
        key="mute",
        translation_key="power_failure_alarm_mute",
        device_class=SensorDeviceClass.ENUM,
        options=["muted", "unmuted"],
        exists_fn=lambda device: device.device_type in ATTR_DEVICE_POWER_FAILURE_ALARM,
        value=lambda value: "muted" if value is True else "unmuted",
    ),
    YoLinkSensorEntityDescription(
        key="sound",
        translation_key="power_failure_alarm_volume",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "medium", "high"],
        exists_fn=lambda device: device.device_type in ATTR_DEVICE_POWER_FAILURE_ALARM,
        value=cvt_volume,
    ),
    YoLinkSensorEntityDescription(
        key="beep",
        translation_key="power_failure_alarm_beep",
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled"],
        exists_fn=lambda device: device.device_type in ATTR_DEVICE_POWER_FAILURE_ALARM,
        value=lambda value: "enabled" if value is True else "disabled",
    ),
    YoLinkSensorEntityDescription(
        key="waterDepth",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        exists_fn=lambda device: device.device_type in ATTR_DEVICE_WATER_DEPTH_SENSOR,
    ),
    YoLinkSensorEntityDescription(
        key="meter_reading",
        translation_key="water_meter_reading",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        should_update_entity=lambda value: value is not None,
        exists_fn=lambda device: device.device_type
        in ATTR_DEVICE_WATER_METER_CONTROLLER,
    ),
    YoLinkSensorEntityDescription(
        key="power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        should_update_entity=lambda value: value is not None,
        exists_fn=lambda device: device.device_model_name in POWER_SUPPORT_MODELS,
        value=lambda value: value / 10 if value is not None else None,
    ),
    YoLinkSensorEntityDescription(
        key="watt",
        translation_key="power_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        should_update_entity=lambda value: value is not None,
        exists_fn=lambda device: device.device_model_name in POWER_SUPPORT_MODELS,
        value=lambda value: value / 100 if value is not None else None,
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
    async_add_entities(
        YoLinkSensorEntity(
            config_entry,
            sensor_device_coordinator,
            description,
        )
        for sensor_device_coordinator in sensor_device_coordinators
        for description in SENSOR_TYPES
        if description.exists_fn(sensor_device_coordinator.device)
    )


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

    @property
    def available(self) -> bool:
        """Return true is device is available."""
        return super().available and self.coordinator.dev_online
