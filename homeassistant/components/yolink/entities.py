"""Entity for YoLink devices."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.light import LightEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.siren import SirenEntity
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


class YoLinkLeakEntity(YoLinkBinarySensorEntity):
    """YoLink Leak Sensor Instance."""

    def __init__(self, device, config_entry):
        """Initialize the YoLink Leak Sensor."""
        super().__init__(device, "LeakSensor", config_entry)

    async def udpate_entity_state(self, water_detected: bool):
        """Update HA Entity State."""
        if water_detected is None:
            return
        self._attr_is_on = water_detected
        await self.async_update_ha_state()

    @property
    def is_on(self):
        """Return WaterLeak State."""
        return self._attr_is_on


class YoLinkMotionEntity(YoLinkBinarySensorEntity):
    """YoLink Motion Sensor Instance."""

    def __init__(self, device: YoLinkDevice, config_entry):
        """Initialize the YoLink Motion Sensor."""
        super().__init__(device, "MotionSensor", config_entry)

    async def udpate_entity_state(self, motion_detected: bool):
        """Update HA Entity State."""
        if motion_detected is None:
            return
        self._attr_is_on = motion_detected
        await self.async_update_ha_state()

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._attr_is_on


class YoLinkTemperatureEntity(YoLinkSensorEntity):
    """YoLink T&H Sensor Instance."""

    def __init__(self, device: YoLinkDevice, config_entry):
        """Initialize the ofYoLink T&H Sensor."""
        super().__init__(device, "temperature", config_entry)

    async def udpate_entity_state(self, temperature: float):
        """Update HA Entity State."""
        if temperature is None:
            return
        self._attr_native_value = temperature
        await self.async_update_ha_state()


class YoLinkHumidityEntity(YoLinkSensorEntity):
    """YoLink T&H Sensor Instance."""

    def __init__(self, device: YoLinkDevice, config_entry):
        """Initialize the ofYoLink T&H Sensor."""
        super().__init__(device, "humidity", config_entry)

    async def udpate_entity_state(self, humidity: float):
        """Update HA Entity State."""
        if humidity is None:
            return
        self._attr_native_value = humidity
        await self.async_update_ha_state()


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


class YoLinkLightEntity(YoLinkDeviceEntity, LightEntity):
    """Representation of a YoLink Outlet."""

    def __init__(self, device: YoLinkDevice, device_type, config_entry):
        """Initialize the YoLink Sensor."""
        super().__init__(device, device_type, config_entry)
        self._attr_is_on = False

    async def udpate_entity_state(self, state: bool):
        """Update HA Entity State."""
        if state is None:
            return
        self._attr_is_on = state
        await self.async_update_ha_state()

    async def async_turn_on_off(self, state: bool):
        """Call *.getState with device to fetch realtime state data."""
        if hasattr(self._yl_device, "async_turn_on_off"):
            async_turn_on_off = getattr(self._yl_device, "async_turn_on_off")
            await async_turn_on_off(self, state)
        else:
            raise NotImplementedError()

    async def async_turn_off(self, **kwargs) -> None:
        """Implement LightEntity.async_turn_off."""
        await self.async_turn_on_off(False)

    async def async_turn_on(self, **kwargs) -> None:
        """Implement LightEntity.async_turn_on."""
        await self.async_turn_on_off(True)


class YoLinkSirenEntity(YoLinkDeviceEntity, SirenEntity):
    """Representation of a YoLink Siren."""

    def __init__(self, device: YoLinkDevice, device_type, config_entry):
        """Initialize the YoLink Sensor."""
        super().__init__(device, device_type, config_entry)
        self._attr_is_on = False

    async def udpate_entity_state(self, state: bool):
        """Update HA Entity State."""
        if state is None:
            return
        self._attr_is_on = state
        await self.async_update_ha_state()

    async def async_turn_on_off(self, state: bool):
        """Response for async_turn_on/async_turn_off."""
        if hasattr(self._yl_device, "async_turn_on_off"):
            async_sire_turn_on_off = getattr(self._yl_device, "async_turn_on_off")
            await async_sire_turn_on_off(state)
        else:
            raise NotImplementedError()

    async def async_turn_off(self, **kwargs) -> None:
        """Implement SirenEntity.async_turn_off."""
        await self.async_turn_on_off(False)

    async def async_turn_on(self, **kwargs) -> None:
        """Implement SirenEntity.async_turn_off."""
        await self.async_turn_on_off(True)
