"""Entity for YoLink devices."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.yolink.device import YoLinkDevice, YoLinkDeviceEntity
from homeassistant.const import TEMP_CELSIUS

"""Sensor Config: Unit : Icon : type"""
SENSOR_TYPES_CONFIG = {
    "DoorSensor": [None, None, "door"],
    "LeakSensor": [None, None, "moisture"],
    "MotionSensor": [None, None, "motion"],
    "temperature": [TEMP_CELSIUS, None, "temperature"],
    "humidity": [None, None, "humidity"],
    "battery": [None, None, "battery"],
}


class YoLinkSensorEntity(YoLinkDeviceEntity, SensorEntity):
    """Representation of a YoLink Sensor."""

    def __init__(self, device: YoLinkDevice, entity_type, config_entry):
        """Initialize the YoLink Sensor."""
        YoLinkDeviceEntity.__init__(self, device, entity_type, config_entry)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        try:
            return SENSOR_TYPES_CONFIG.get(self._type)[1]
        except TypeError:
            return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SENSOR_TYPES_CONFIG.get(self._type)[0]
        except TypeError:
            return None

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return (
            SENSOR_TYPES_CONFIG.get(self._type)[2]
            if self._type in SENSOR_TYPES_CONFIG
            else None
        )


class YoLinkBinarySensorEntity(YoLinkDeviceEntity, BinarySensorEntity):
    """Representation of a YoLink Sensor."""

    @property
    def device_class(self):
        """Class type of device."""
        if self._type in SENSOR_TYPES_CONFIG:
            return SENSOR_TYPES_CONFIG.get(self._type)[2]
        raise NotImplementedError("Binary Sensor not implemented:" + self._type)

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return False


class YoLinkBatteryEntity(YoLinkSensorEntity):
    """YoLink Battery Entity."""

    def __init__(self, device: YoLinkDevice, config_entry):
        """Initialize the ofYoLink T&H Sensor."""
        super().__init__(device, "battery", config_entry)

    async def udpate_entity_state(self, level: int):
        """Update HA Entity State."""
        if level is None:
            return
        if level >= 4:
            self._attr_native_value = 100
        elif level >= 3:
            self._attr_native_value = 70
        elif level >= 2:
            self._attr_native_value = 50
        elif level >= 1:
            self._attr_native_value = 20
        else:
            self._attr_native_value = 5
        await self.async_update_ha_state()


class YoLinkDoorEntity(YoLinkBinarySensorEntity):
    """YoLink Door Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the YoLink Door Sensor."""
        super().__init__(device, "DoorSensor", config_entry)

    async def udpate_entity_state(self, concat: bool):
        """Update HA Entity State."""
        if concat is None:
            return
        self._attr_is_on = concat
        await self.async_update_ha_state()

    @property
    def is_on(self):
        """Ueturn Door State."""
        return self._attr_is_on
