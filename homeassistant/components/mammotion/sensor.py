"""Creates the sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    AREA_SQUARE_METERS,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_conversion import SpeedConverter
from pymammotion.data.model.device import MowingDevice
from pymammotion.data.model.enums import RTKStatus
from pymammotion.utility.constant.device_constant import (
    PosType,
    device_connection,
    device_mode,
)
from pymammotion.utility.device_type import DeviceType

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity

SPEED_UNITS = SpeedConverter.VALID_UNITS


@dataclass(frozen=True, kw_only=True)
class MammotionSensorEntityDescription(SensorEntityDescription):
    """Describes Mammotion sensor entity."""

    value_fn: Callable[[MowingDevice], StateType]


LUBA_SENSOR_ONLY_TYPES: tuple[MammotionSensorEntityDescription, ...] = (
    MammotionSensorEntityDescription(
        key="blade_height",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        value_fn=lambda mower_data: mower_data.report_data.work.knife_height,
    ),
)

SENSOR_TYPES: tuple[MammotionSensorEntityDescription, ...] = (
    MammotionSensorEntityDescription(
        key="battery_percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda mower_data: mower_data.report_data.dev.battery_val,
    ),
    MammotionSensorEntityDescription(
        key="ble_rssi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value_fn=lambda mower_data: mower_data.report_data.connect.ble_rssi,
    ),
    MammotionSensorEntityDescription(
        key="wifi_rssi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value_fn=lambda mower_data: mower_data.report_data.connect.wifi_rssi,
    ),
    MammotionSensorEntityDescription(
        key="connect_type",
        device_class=SensorDeviceClass.ENUM,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: device_connection(
            mower_data.report_data.connect.connect_type,
            mower_data.report_data.connect.used_net,
        ),
    ),
    MammotionSensorEntityDescription(
        key="maintenance_distance",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda mower_data: mower_data.report_data.maintenance.mileage,
    ),
    MammotionSensorEntityDescription(
        key="maintenance_work_time",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda mower_data: mower_data.report_data.maintenance.work_time,
    ),
    MammotionSensorEntityDescription(
        key="maintenance_bat_cycles",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: mower_data.report_data.maintenance.bat_cycles,
    ),
    MammotionSensorEntityDescription(
        key="gps_stars",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: mower_data.report_data.rtk.gps_stars,
    ),
    MammotionSensorEntityDescription(
        key="area",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
        native_unit_of_measurement=AREA_SQUARE_METERS,
        value_fn=lambda mower_data: mower_data.report_data.work.area & 65535,
    ),
    MammotionSensorEntityDescription(
        key="mowing_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda mower_data: mower_data.report_data.work.man_run_speed / 100,
    ),
    MammotionSensorEntityDescription(
        key="progress",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda mower_data: mower_data.report_data.work.area >> 16,
    ),
    MammotionSensorEntityDescription(
        key="total_time",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda mower_data: mower_data.report_data.work.progress & 65535,
    ),
    MammotionSensorEntityDescription(
        key="elapsed_time",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda mower_data: (mower_data.report_data.work.progress & 65535)
        - (mower_data.report_data.work.progress >> 16),
    ),
    MammotionSensorEntityDescription(
        key="left_time",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda mower_data: mower_data.report_data.work.progress >> 16,
    ),
    MammotionSensorEntityDescription(
        key="l1_satellites",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: (mower_data.report_data.rtk.co_view_stars >> 0)
        & 255,
    ),
    MammotionSensorEntityDescription(
        key="l2_satellites",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: (mower_data.report_data.rtk.co_view_stars >> 8)
        & 255,
    ),
    MammotionSensorEntityDescription(
        key="activity_mode",
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda mower_data: device_mode(mower_data.report_data.dev.sys_status),
    ),
    MammotionSensorEntityDescription(
        key="position_mode",
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: str(
            RTKStatus.from_value(mower_data.report_data.rtk.status)
        ),  # Note: This will not work for Luba2 & Yuka. Only for Luba1
    ),
    MammotionSensorEntityDescription(
        key="position_type",
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: str(
            PosType(mower_data.location.position_type).name
        ),  # Note: This will not work for Luba2 & Yuka. Only for Luba1
    ),
    MammotionSensorEntityDescription(
        key="work_area",
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
        native_unit_of_measurement=None,
        value_fn=lambda mower_data: str(mower_data.location.work_zone or "Not working"),
    ),
    # MammotionSensorEntityDescription(
    #     key="lawn_mower_position",
    #     state_class=None,
    #     device_class=None,  # Set device class to "geo_location"
    #     native_unit_of_measurement=None,
    #     value_fn=lambda mower_data: f"{mower_data.location.device.latitude}, {mower_data.location.device.longitude}"
    # )
    # ToDo: We still need to add the following.
    # - RTK Status - None, Single, Fix, Float, Unknown (RTKStatusFragment.java)
    # - Signal quality (Robot)
    # - Signal quality (Ref. Station)
    # - LoRa number
    # - Multi-point turn
    # - Transverse mode
    # - WiFi status
    # - Side LED
    # - Possibly more I forgot about
    # 'real_pos_x': -142511, 'real_pos_y': -20548, 'real_toward': 50915, (robot position)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data

    if not DeviceType.is_yuka(coordinator.device_name):
        async_add_entities(
            MammotionSensorEntity(coordinator, description)
            for description in LUBA_SENSOR_ONLY_TYPES
        )

    async_add_entities(
        MammotionSensorEntity(coordinator, description) for description in SENSOR_TYPES
    )


class MammotionSensorEntity(MammotionBaseEntity, SensorEntity):
    """Defining the Mammotion Sensor."""

    entity_description: MammotionSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        description: MammotionSensorEntityDescription,
    ) -> None:
        """Set up MammotionSensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        current_value = self.entity_description.value_fn(self.coordinator.data)
        return current_value
