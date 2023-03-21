"""Binary sensor descriptions for Solvis Max binary sensor data."""
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)


@dataclass
class SolvisMaxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes SolvisMax binary sensor entity."""


BINARY_SENSOR_TYPES: tuple[SolvisMaxBinarySensorEntityDescription, ...] = (
    SolvisMaxBinarySensorEntityDescription(
        key="A1", name="solar pump", device_class=BinarySensorDeviceClass.HEAT
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A2",
        name="warm water station pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A3",
        name="heating circuit 1 pump",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A4",
        name="heating circuit 2 pump",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A5",
        name="circulation pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A6",
        name="heating circuit 3 pump",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A7",
        name="solar 2 pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A8",
        name="heating circuit 1 mixer open",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A9",
        name="heating circuit 1 mixer close",
        device_class=BinarySensorDeviceClass.COLD,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A10",
        name="heating circuit 2 mixer open",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A11",
        name="heating circuit 2 mixer close",
        device_class=BinarySensorDeviceClass.COLD,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A12",
        name="burner",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A13",
        name="burner s2",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    SolvisMaxBinarySensorEntityDescription(
        key="A14",
        name="recovery",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)
