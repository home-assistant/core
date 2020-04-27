"""Representation of Z-Wave binary_sensors."""

import logging

from openzwavemqtt.const import ValueType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_SOUND,
    BinarySensorDevice,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity, create_device_name

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAPPING = {
    # Mapping from Value Index in Notification CC to device class
    1: DEVICE_CLASS_SMOKE,
    2: DEVICE_CLASS_GAS,
    3: DEVICE_CLASS_GAS,
    4: DEVICE_CLASS_HEAT,
    5: DEVICE_CLASS_MOISTURE,
    6: DEVICE_CLASS_SAFETY,
    7: DEVICE_CLASS_SAFETY,
    8: DEVICE_CLASS_POWER,
    9: DEVICE_CLASS_PROBLEM,
    10: DEVICE_CLASS_PROBLEM,
    14: DEVICE_CLASS_SOUND,
    15: DEVICE_CLASS_MOISTURE,
    18: DEVICE_CLASS_GAS,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave binary_sensor from config entry."""

    @callback
    def async_add_binary_sensor(values):
        """Add Z-Wave Binary Sensor."""
        sensors_to_add = []

        if values.primary.type == ValueType.LIST:

            # Handle special cases
            # we convert some of the Notification values into it's own binary sensor
            # https://github.com/OpenZWave/open-zwave/blob/master/config/NotificationCCTypes.xml
            # TODO: Use constants/Enums from lib (when added)
            for item in values.primary.value["List"]:
                if values.primary.index == 6 and item["Value"] == 22:
                    # Door/Window Open
                    sensors_to_add.append(
                        ZWaveListValueSensor(values, item["Value"], DEVICE_CLASS_DOOR)
                    )
                if values.primary.index == 7 and item["Value"] in [7, 8]:
                    # Motion detected
                    sensors_to_add.append(
                        ZWaveListValueSensor(values, item["Value"], DEVICE_CLASS_MOTION)
                    )

            # Fallback to a generic binary sensor for the notification topic
            if not sensors_to_add:
                sensors_to_add.append(ZWaveListSensor(values))

        elif values.primary.type == ValueType.BOOL:
            # classic/legacy binary sensor
            sensors_to_add.append(ZWaveBinarySensor(values))
        else:
            # should not happen but just in case log it while we're in beta
            _LOGGER.warning("Sensor not implemented for value %s", values.primary.label)
            return

        async_add_entities(sensors_to_add)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, "zwave_new_binary_sensor", async_add_binary_sensor
        )
    )

    await hass.data[DOMAIN][config_entry.entry_id]["mark_platform_loaded"](
        "binary_sensor"
    )


class ZWaveBinarySensor(ZWaveDeviceEntity, BinarySensorDevice):
    """Representation of a Z-Wave binary_sensor."""

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self.values.primary.value

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Legacy binary sensors are phased out (replaced by notification sensors)
        # Disable by default to not confuse users
        return False


class ZWaveListSensor(ZWaveDeviceEntity, BinarySensorDevice):
    """Representation of a ZWaveListSensor translated to binary_sensor."""

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self.values.primary.value["Selected"] != "Clear"

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = super().device_state_attributes
        attributes["event"] = self.values.primary.value["Selected"]
        return attributes

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_MAPPING.get(self.values.primary.index)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some of the more advanced sensors by default to not overwhelm users
        if self.values.primary.index in [8, 9]:
            return False
        return True


class ZWaveListValueSensor(ZWaveDeviceEntity, BinarySensorDevice):
    """Representation of a ZWaveListValueSensor binary_sensor."""

    def __init__(self, values, list_value, device_class=None):
        """Initialize a ZWaveListValueSensor entity."""
        self._list_value = list_value
        self._device_class = device_class
        super().__init__(values)

    @property
    def name(self):
        """Return the name of the entity."""
        node = self.values.primary.node
        value_label = ""
        for item in self.values.primary.value["List"]:
            if item["Value"] == self._list_value:
                value_label = item["Label"]
                break
        value_label = value_label.split(" on ")[0]  # strip "on location" from name
        value_label = value_label.split(" at ")[0]  # strip "at location" from name
        return f"{create_device_name(node)}: {value_label}"

    @property
    def unique_id(self):
        """Return the unique_id of the entity."""
        unique_id = super().unique_id
        return f"{unique_id}.{self._list_value}"

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self.values.primary.value["Selected_id"] == self._list_value

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class
