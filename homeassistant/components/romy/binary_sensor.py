"""Binary Sensors from your ROMY."""

import json
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
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

    romy_binary_sensor_entitiy_docked = RomyBinarySensor(
        host, port, name, unique_id, device_info, None, "Dustbin present", "dustbin"
    )
    romy_binary_sensor_entitiy_dustbin_present = RomyBinarySensor(
        host,
        port,
        name,
        unique_id,
        device_info,
        BinarySensorDeviceClass.PRESENCE,
        "Robot docked",
        "dock",
    )
    romy_binary_sensor_entitiy_watertank_present = RomyBinarySensor(
        host,
        port,
        name,
        unique_id,
        device_info,
        BinarySensorDeviceClass.MOISTURE,
        "Watertank present",
        "water_tank",
    )
    romy_binary_sensor_entitiy_watertank_empty = RomyBinarySensor(
        host,
        port,
        name,
        unique_id,
        device_info,
        BinarySensorDeviceClass.PROBLEM,
        "Watertank empty",
        "water_tank_empty",
    )

    # sensor list
    romy_binary_sensor_entities = [
        romy_binary_sensor_entitiy_docked,
        romy_binary_sensor_entitiy_dustbin_present,
        romy_binary_sensor_entitiy_watertank_present,
        romy_binary_sensor_entitiy_watertank_empty,
    ]

    # fetch information which sensors are present and add it in case
    binary_sensor_entities = []
    ret, response = await async_query(hass, host, port, "get/sensor_status")
    if ret:
        status = json.loads(response)
        hal_status = status["hal_status"]
        for sensor in hal_status["sensor_list"]:
            for romy_binary_sensor_entity in romy_binary_sensor_entities:
                if (
                    sensor["is_registered"] == 1
                    and sensor["device_descriptor"]
                    == romy_binary_sensor_entity.device_descriptor
                ):
                    binary_sensor_entities.append(romy_binary_sensor_entity)

    else:
        _LOGGER.error("Error fetching sensor status resp: %s", response)

    async_add_entities(binary_sensor_entities, True)


class RomyBinarySensor(BinarySensorEntity):
    """RomyBinarySensor Class."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        unique_id: str,
        device_info: dict[str, Any],
        device_class: BinarySensorDeviceClass | None,
        sensor_name: str,
        device_descriptor: str,
    ) -> None:
        """Initialize ROMYs BinarySensor."""
        self._host = host
        self._port = port
        self._name = name
        self._attr_unique_id = unique_id
        self._attr_device_class = device_class
        self._sensor_value = False
        self._sensor_name = sensor_name
        self._device_descriptor = device_descriptor

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def device_descriptor(self) -> str:
        """Return the device_descriptor of this sensor."""
        return self._device_descriptor

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._device_descriptor}_{self._attr_unique_id}"

    async def async_update(self) -> None:
        """Fetch value from the device."""
        ret, response = await async_query(
            self.hass, self._host, self._port, "get/sensor_values"
        )
        if ret:
            self._sensor_value = False
            sensor_values = json.loads(response)
            for sensor in sensor_values["sensor_data"]:
                if sensor["device_type"] == "gpio":
                    gpio_sensors = sensor["sensor_data"]
                    for gpio_sensor in gpio_sensors:
                        if (
                            gpio_sensor["device_descriptor"] == self._device_descriptor
                            and gpio_sensor["payload"]["data"]["value"] == "active"
                        ):
                            self._sensor_value = True
        else:
            _LOGGER.error(
                "%s async_update -> async_query response: %s",
                self._sensor_name,
                response,
            )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self._sensor_value
