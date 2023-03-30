"""Binary sensor descriptions for binary sensor data."""
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)


@dataclass
class SolvisMaxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes SolvisMax binary sensor entity."""


BINARY_SENSOR_TYPES_BASE: tuple[SolvisMaxBinarySensorEntityDescription, ...] = (
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_1_pump",
        translation_key="heating_circuit_1_pump",
        name="heating circuit 1 pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_2_pump",
        translation_key="heating_circuit_2_pump",
        name="heating circuit 2 pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_3_pump",
        translation_key="heating_circuit_3_pump",
        name="heating circuit 3 pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_1_mixer_open",
        translation_key="heating_circuit_1_mixer_open",
        name="heating circuit 1 mixer open",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_1_mixer_close",
        translation_key="heating_circuit_1_mixer_close",
        name="heating circuit 1 mixer close",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_2_mixer_open",
        translation_key="heating_circuit_2_mixer_open",
        name="heating circuit 2 mixer open",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="heating_circuit_2_mixer_close",
        translation_key="heating_circuit_2_mixer_close",
        name="heating circuit 2 mixer close",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="burner",
        translation_key="burner",
        name="burner",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="burner_s2",
        translation_key="burner_s2",
        name="burner s2",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="recovery",
        translation_key="recovery",
        name="recovery",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)
BINARY_SENSOR_TYPES_WARMWATER: tuple[SolvisMaxBinarySensorEntityDescription, ...] = (
    SolvisMaxBinarySensorEntityDescription(
        key="warm_water_station_pump",
        translation_key="warm_water_station_pump",
        name="warm water station pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="circulation_pump",
        translation_key="circulation_pump",
        name="circulation pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)
BINARY_SENSOR_TYPES_SOLAR = SolvisMaxBinarySensorEntityDescription(
    key="solar_pump",
    translation_key="solar_pump",
    name="solar pump",
    device_class=BinarySensorDeviceClass.RUNNING,
)
BINARY_SENSOR_TYPES_SOLAR_EAST_WEST: tuple[
    SolvisMaxBinarySensorEntityDescription, ...
] = (
    SolvisMaxBinarySensorEntityDescription(
        key="solar_valve_1",
        translation_key="solar_valve_1",
        name="solar valve 1",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="solar_valve_2",
        translation_key="solar_valve_2",
        name="solar valve 2",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)
BINARY_SENSOR_TYPES_OVEN = SolvisMaxBinarySensorEntityDescription(
    key="oven_pump",
    translation_key="oven_pump",
    name="oven pump",
    device_class=BinarySensorDeviceClass.RUNNING,
)
