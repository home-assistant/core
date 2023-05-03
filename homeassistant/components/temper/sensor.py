"""Support for getting temperature from TEMPer devices."""
from __future__ import annotations

import logging

from temperusb.temper import TemperHandler
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OFFSET,
    DEVICE_DEFAULT_NAME,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SCALE = "scale"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
        temperature_description = SensorEntityDescription(
            key=f"temper_{dev.type.name}_temperature",
            name=f"{name} temperature",
            icon="mdi:thermometer",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=1,
        )
        TEMPER_SENSORS.append(TemperatureSensor(dev, temperature_description, scaling))
        if dev.lookup_humidity_offset(0) is not None:
            humidity_description = SensorEntityDescription(
                key=f"temper_{dev.type.name}_humidity",
                name=f"{name} humidity",
                icon="mdi:water-percent",
                device_class=SensorDeviceClass.HUMIDITY,
                native_unit_of_measurement=PERCENTAGE,
                suggested_display_precision=1,
            )
            TEMPER_SENSORS.append(HumiditySensor(dev, humidity_description))
    add_entities(TEMPER_SENSORS)


def reset_devices():
    """Re-scan for underlying Temper sensors and assign them to our devices.

    This assumes the same sensor devices are present in the same order.
    """
    temper_devices = get_temper_devices()
    for sensor, device in zip(TEMPER_SENSORS, temper_devices):
        sensor.set_temper_device(device)


class TemperatureSensor(SensorEntity):
    """Representation of a Temper temperature sensor."""

    def __init__(self, temper_device, description, scaling):
        """Initialize the sensor."""
        self.scale = scaling["scale"]
        self.offset = scaling["offset"]
        self.set_temper_device(temper_device)

        self._attr_unique_id = description.key
        self.entity_description = description

    def set_temper_device(self, temper_device):
        """Assign the underlying device for this sensor."""
        self.temper_device = temper_device

        # set calibration data
        self.temper_device.set_calibration_data(scale=self.scale, offset=self.offset)

    def update(self) -> None:
        """Retrieve latest state."""
        try:
            self._attr_native_value = self.temper_device.get_temperature("celsius")
        except OSError:
            _LOGGER.error(
                "Failed to get temperature. The device address may"
                "have changed. Attempting to reset device"
            )
            reset_devices()

class HumiditySensor(SensorEntity):
    """Representation of a Temper humidity sensor."""

    def __init__(self, temper_device, description):
        """Initialize the sensor."""
        self._attr_unique_id = description.key
        self.entity_description = description
        self.temper_device = temper_device

    def update(self) -> None:
        """Retrieve latest state."""
        try:
            self._attr_native_value = self.temper_device.get_humidity()[0]['humidity_pc']
        except:
            _LOGGER.warning(
                "A humidity sensor was detected, but no humidity was returned."
            )
