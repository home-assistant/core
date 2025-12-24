"""Support for Vera sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import pyvera as veraApi

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import ControllerData, get_controller_data
from .entity import VeraEntity

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    entities: list[SensorEntity] = []

    # Add regular sensors
    entities.extend(
        VeraSensor(device, controller_data)
        for device in controller_data.devices[Platform.SENSOR]
    )

    # Add power/energy sensors for switches and lights that support energy monitoring
    for device in controller_data.devices.get(Platform.SWITCH, []):
        power = getattr(device, "power", None)
        if (
            power is not None
            and not callable(power)
            and (isinstance(power, (int, float)))
        ):
            entities.append(VeraPowerSensor(device, controller_data))
        energy = getattr(device, "energy", None)
        if (
            energy is not None
            and not callable(energy)
            and (isinstance(energy, (int, float)))
        ):
            entities.append(VeraEnergySensor(device, controller_data))

    for device in controller_data.devices.get(Platform.LIGHT, []):
        power = getattr(device, "power", None)
        if (
            power is not None
            and not callable(power)
            and (isinstance(power, (int, float)))
        ):
            entities.append(VeraPowerSensor(device, controller_data))
        energy = getattr(device, "energy", None)
        if (
            energy is not None
            and not callable(energy)
            and (isinstance(energy, (int, float)))
        ):
            entities.append(VeraEnergySensor(device, controller_data))

    async_add_entities(entities, True)


class VeraSensor(VeraEntity[veraApi.VeraSensor], SensorEntity):
    """Representation of a Vera Sensor."""

    def __init__(
        self, vera_device: veraApi.VeraSensor, controller_data: ControllerData
    ) -> None:
        """Initialize the sensor."""
        self._temperature_units: str | None = None
        self.last_changed_time = None
        VeraEntity.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)
        if self.vera_device.category == veraApi.CATEGORY_TEMPERATURE_SENSOR:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif self.vera_device.category == veraApi.CATEGORY_LIGHT_SENSOR:
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        elif self.vera_device.category == veraApi.CATEGORY_HUMIDITY_SENSOR:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
        elif self.vera_device.category == veraApi.CATEGORY_POWER_METER:
            self._attr_device_class = SensorDeviceClass.POWER
        if self.vera_device.category == veraApi.CATEGORY_LIGHT_SENSOR:
            self._attr_native_unit_of_measurement = LIGHT_LUX
        elif self.vera_device.category == veraApi.CATEGORY_UV_SENSOR:
            self._attr_native_unit_of_measurement = "level"
        elif self.vera_device.category == veraApi.CATEGORY_HUMIDITY_SENSOR:
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif self.vera_device.category == veraApi.CATEGORY_POWER_METER:
            self._attr_native_unit_of_measurement = UnitOfPower.WATT

    def update(self) -> None:
        """Update the state."""
        super().update()
        if self.vera_device.category == veraApi.CATEGORY_TEMPERATURE_SENSOR:
            self._attr_native_value = self.vera_device.temperature

            vera_temp_units = self.vera_device.vera_controller.temperature_units

            if vera_temp_units == "F":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

        elif self.vera_device.category in (
            veraApi.CATEGORY_LIGHT_SENSOR,
            veraApi.CATEGORY_UV_SENSOR,
        ):
            self._attr_native_value = self.vera_device.light
        elif self.vera_device.category == veraApi.CATEGORY_HUMIDITY_SENSOR:
            self._attr_native_value = self.vera_device.humidity
        elif self.vera_device.category == veraApi.CATEGORY_SCENE_CONTROLLER:
            controller = cast(veraApi.VeraSceneController, self.vera_device)
            value = controller.get_last_scene_id(True)
            time = controller.get_last_scene_time(True)
            if time == self.last_changed_time:
                self._attr_native_value = None
            else:
                self._attr_native_value = value
            self.last_changed_time = time
        elif self.vera_device.category == veraApi.CATEGORY_POWER_METER:
            self._attr_native_value = self.vera_device.power
        elif self.vera_device.is_trippable:
            tripped = self.vera_device.is_tripped
            self._attr_native_value = "Tripped" if tripped else "Not Tripped"
        else:
            self._attr_native_value = "Unknown"


class VeraPowerSensor(
    VeraEntity[veraApi.VeraSwitch | veraApi.VeraDimmer], SensorEntity
):
    """Representation of a Vera Power Sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        vera_device: veraApi.VeraSwitch | veraApi.VeraDimmer,
        controller_data: ControllerData,
    ) -> None:
        """Initialize the power sensor."""
        VeraEntity.__init__(self, vera_device, controller_data)
        # Use a unique entity_id and unique_id for the power sensor
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.vera_id}_power")
        self._unique_id = f"{self._unique_id}_power"
        self._attr_name = "Power"
        self._attr_translation_key = "power"

    def update(self) -> None:
        """Update the state."""
        super().update()
        power = getattr(self.vera_device, "power", None)
        if power is not None:
            self._attr_native_value = power


class VeraEnergySensor(
    VeraEntity[veraApi.VeraSwitch | veraApi.VeraDimmer], SensorEntity
):
    """Representation of a Vera Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        vera_device: veraApi.VeraSwitch | veraApi.VeraDimmer,
        controller_data: ControllerData,
    ) -> None:
        """Initialize the energy sensor."""
        VeraEntity.__init__(self, vera_device, controller_data)
        # Use a unique entity_id and unique_id for the energy sensor
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.vera_id}_energy")
        self._unique_id = f"{self._unique_id}_energy"
        self._attr_name = "Energy"
        self._attr_translation_key = "energy"

    def update(self) -> None:
        """Update the state."""
        super().update()
        energy = getattr(self.vera_device, "energy", None)
        if energy is not None:
            self._attr_native_value = energy
