"""Support for getting temperature from TEMPer devices."""

from __future__ import annotations

import logging

from temperusb.temper import TemperHandler
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OFFSET,
    DEVICE_DEFAULT_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SCALE = "scale"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): vol.Coerce(str),
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
    }
)

TEMPER_SENSORS: list[TemperSensor] = []


def get_temper_devices():
    """Scan the Temper devices from temperusb."""
    return TemperHandler().get_devices()


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Temper sensors."""
    prefix = name = config[CONF_NAME]
    scaling = {"scale": config.get(CONF_SCALE), "offset": config.get(CONF_OFFSET)}
    temper_devices = get_temper_devices()

    for idx, dev in enumerate(temper_devices):
        if idx != 0:
            name = f"{prefix}_{idx!s}"
        TEMPER_SENSORS.append(TemperSensor(dev, name, scaling))
    add_entities(TEMPER_SENSORS)


def reset_devices():
    """Re-scan for underlying Temper sensors and assign them to our devices.

    This assumes the same sensor devices are present in the same order.
    """
    temper_devices = get_temper_devices()
    for sensor, device in zip(TEMPER_SENSORS, temper_devices, strict=False):
        sensor.set_temper_device(device)


class TemperSensor(SensorEntity):
    """Representation of a Temper temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, temper_device, name, scaling):
        """Initialize the sensor."""
        self.scale = scaling["scale"]
        self.offset = scaling["offset"]
        self.set_temper_device(temper_device)

        self._attr_name = name

    def set_temper_device(self, temper_device):
        """Assign the underlying device for this sensor."""
        self.temper_device = temper_device

        # set calibration data
        self.temper_device.set_calibration_data(scale=self.scale, offset=self.offset)

    def update(self) -> None:
        """Retrieve latest state."""
        try:
            sensor_value = self.temper_device.get_temperature("celsius")
            self._attr_native_value = round(sensor_value, 1)
        except OSError:
            _LOGGER.error(
                "Failed to get temperature. The device address may"
                "have changed. Attempting to reset device"
            )
            reset_devices()
