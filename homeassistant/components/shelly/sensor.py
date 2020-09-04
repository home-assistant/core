"""Sensor for Shelly."""
import aioshelly

from homeassistant.components import sensor
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
    VOLT,
)
from homeassistant.helpers.entity import Entity

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN

SENSORS = {
    "battery": [UNIT_PERCENTAGE, sensor.DEVICE_CLASS_BATTERY],
    "concentration": [CONCENTRATION_PARTS_PER_MILLION, None],
    "current": [ELECTRICAL_CURRENT_AMPERE, sensor.DEVICE_CLASS_CURRENT],
    "deviceTemp": [None, sensor.DEVICE_CLASS_TEMPERATURE],
    "energy": [ENERGY_KILO_WATT_HOUR, sensor.DEVICE_CLASS_ENERGY],
    "energyReturned": [ENERGY_KILO_WATT_HOUR, sensor.DEVICE_CLASS_ENERGY],
    "extTemp": [None, sensor.DEVICE_CLASS_TEMPERATURE],
    "humidity": [UNIT_PERCENTAGE, sensor.DEVICE_CLASS_HUMIDITY],
    "overpowerValue": [POWER_WATT, sensor.DEVICE_CLASS_POWER],
    "power": [POWER_WATT, sensor.DEVICE_CLASS_POWER],
    "voltage": [VOLT, sensor.DEVICE_CLASS_VOLTAGE],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []

    for block in wrapper.device.blocks:
        for attr in SENSORS:
            # Filter out non-existing sensors and sensors without a value
            if getattr(block, attr, None) is None:
                continue

            sensors.append(ShellySensor(wrapper, block, attr))

    if sensors:
        async_add_entities(sensors)


class ShellySensor(ShellyBlockEntity, Entity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        block: aioshelly.Block,
        attribute: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, block)
        self.attribute = attribute
        unit, device_class = SENSORS[attribute]
        self.info = block.info(attribute)

        if (
            self.info[aioshelly.BLOCK_VALUE_TYPE]
            == aioshelly.BLOCK_VALUE_TYPE_TEMPERATURE
        ):
            if self.info[aioshelly.BLOCK_VALUE_UNIT] == "C":
                unit = TEMP_CELSIUS
            else:
                unit = TEMP_FAHRENHEIT

        self._unit = unit
        self._device_class = device_class

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{super().unique_id}-{self.attribute}"

    @property
    def name(self):
        """Name of sensor."""
        return f"{self.wrapper.name} - {self.attribute}"

    @property
    def state(self):
        """Value of sensor."""
        value = getattr(self.block, self.attribute)
        if value is None:
            return None

        if self.attribute in [
            "deviceTemp",
            "extTemp",
            "humidity",
            "overpowerValue",
            "power",
        ]:
            return round(value, 1)
        # Energy unit change from Wmin or Wh to kWh
        if self.info.get(aioshelly.BLOCK_VALUE_UNIT) == "Wmin":
            return round(value / 60 / 1000, 2)
        if self.info.get(aioshelly.BLOCK_VALUE_UNIT) == "Wh":
            return round(value / 1000, 2)
        return value

    @property
    def unit_of_measurement(self):
        """Return unit of sensor."""
        return self._unit

    @property
    def device_class(self):
        """Device class of sensor."""
        return self._device_class

    @property
    def available(self):
        """Available."""
        if self.attribute == "concentration":
            # "sensorOp" is "normal" when the Shelly Gas is working properly and taking
            # measurements.
            return super().available and self.block.sensorOp == "normal"
        return super().available
