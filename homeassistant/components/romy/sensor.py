"""Sensor checking adc and status values from your ROMY."""

import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .utils import async_query

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY sensor with config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    name = config_entry.data[CONF_NAME]
    unique_id = ""
    model = ""
    firmware = ""

    ret, response = await async_query(hass, host, port, "get/robot_id")
    if ret:
        status = json.loads(response)
        unique_id = status["unique_id"]
        model = status["model"]
        firmware = status["firmware"]
    else:
        _LOGGER.error("Error fetching unique_id resp: %s", response)

    device_info = {
        "manufacturer": "ROMY",
        "model": model,
        "sw_version": firmware,
        "identifiers": {"serial": unique_id},
    }

    romy_status_sensor_entitiy_battery = RomyStatusSensor(
        host,
        port,
        name,
        unique_id,
        device_info,
        SensorDeviceClass.BATTERY,
        "Battery Level",
        "battery_level",
        "get/status",
        PERCENTAGE,
    )
    romy_status_sensor_entitiy_rssi = RomyStatusSensor(
        host,
        port,
        name,
        unique_id,
        device_info,
        SensorDeviceClass.SIGNAL_STRENGTH,
        "RSSI Level",
        "rssi",
        "get/wifi_status",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    )

    # add status sensors
    romy_status_sensor_entities = [
        romy_status_sensor_entitiy_battery,
        romy_status_sensor_entitiy_rssi,
    ]
    async_add_entities(romy_status_sensor_entities, True)

    romy_adc_sensor_entitiy_dustbin_full = RomyAdcSensor(
        host, port, name, unique_id, device_info, "Dustbin Full Level", "dustbin_sensor"
    )

    # fetch information which sensors are present and add it in case
    adc_sensor_entities = []
    ret, response = await async_query(hass, host, port, "get/sensor_status")
    if ret:
        status = json.loads(response)
        hal_status = status["hal_status"]
        for sensor in hal_status["sensor_list"]:
            if sensor["device_descriptor"] == "dustbin_sensor":
                if sensor["is_registered"] == 1:
                    adc_sensor_entities.append(romy_adc_sensor_entitiy_dustbin_full)
    else:
        _LOGGER.error("Error fetching sensor status resp: %s", response)

    async_add_entities(adc_sensor_entities, True)


class RomyStatusSensor(SensorEntity):
    """RomyStatusSensor Class."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        unique_id: str,
        device_info: dict[str, Any],
        device_class: SensorDeviceClass,
        sensor_name: str,
        sensor_descriptor: str,
        sensor_command: str,
        measurement_unit: str,
    ) -> None:
        """Initialize ROMYs BatterySensor."""
        self._sensor_value = None
        self._name = name
        self._host = host
        self._port = port
        self._attr_unique_id = unique_id
        self._device_info = device_info
        self._device_class = device_class
        self._sensor_name = sensor_name
        self._sensor_descriptor = sensor_descriptor
        self._sensor_command = sensor_command
        self._measurement_unit = measurement_unit

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._sensor_descriptor}_{self._attr_unique_id}"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement of the device."""
        return self._measurement_unit

    async def async_update(self) -> None:
        """Fetch the sensor state from the device."""
        ret, response = await async_query(
            self.hass, self._host, self._port, self._sensor_command
        )
        _LOGGER.debug(
            "ROMY %s async_update -> async_query ret:%s, response: %s",
            self.name,
            ret,
            response,
        )
        if ret:
            status = json.loads(response)
            self._sensor_value = status[self._sensor_descriptor]
        else:
            _LOGGER.error(
                "%s async_update -> async_query response: %s",
                self.name,
                response,
            )

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        return self._sensor_value


class RomyAdcSensor(SensorEntity):
    """RomyAdcSensor Class."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        unique_id: str,
        device_info: dict[str, Any],
        sensor_name: str,
        sensor_descriptor: str,
    ) -> None:
        """Initialize ROMYs DustbinFullSensor."""
        self._sensor_value = None
        self._name = name
        self._host = host
        self._port = port
        self._attr_unique_id = unique_id
        self._device_info = device_info
        self._sensor_name = sensor_name
        self._sensor_descriptor = sensor_descriptor

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._sensor_descriptor}_{self._attr_unique_id}"

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        """Fetch adc value from the device."""
        ret, response = await async_query(
            self.hass, self._host, self._port, "get/sensor_values"
        )
        if ret:
            sensor_values = json.loads(response)
            for sensor in sensor_values["sensor_data"]:
                if sensor["device_type"] == "adc":
                    adc_sensors = sensor["sensor_data"]
                    for adc_sensor in adc_sensors:
                        if adc_sensor["device_descriptor"] == self._sensor_descriptor:
                            self._sensor_value = adc_sensor["payload"]["data"][
                                "values"
                            ][0]

    @property
    def native_value(self) -> int | None:
        """Return the adc value of the sensor."""
        return self._sensor_value
