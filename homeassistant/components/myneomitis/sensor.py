"""Sensor platform for MyNeomitis integration."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .utils import CtnType, Sensors, get_device_by_rfid, parents_to_dict

_LOGGER = logging.getLogger(__name__)

SUB_MODELES = ["UFH"]


class DevicesEnergySensor(SensorEntity):
    """Sensor for tracking MyNeomitis devices energy consumption."""

    def __init__(self, api: Any, device: dict[str, Any], base_offset: float) -> None:
        """Initialize the devices energy sensor.

        Args:
            api: The API client used to interact with the device.
            device: The device information containing name, ID, and state.
            base_offset: Current consumption data of the devices

        """
        self._api = api
        self._device = device
        self._attr_name = f"MyNeo {device['name']} Energy"
        self._attr_unique_id = f"myneo_{device['_id']}_energy"
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_should_poll = True
        self._initial_consumption = base_offset

    @property
    def native_value(self) -> float:
        """Return the current energy consumption in kWh."""
        current = round(self._device['state']['consumption'] / 1000, 3)
        return max(0.0, round(current - self._initial_consumption, 3))

    async def async_update(self) -> None:
        """Fetch the latest state of devices from the API.

        This method retrieves the current state of the device.
        """
        state = await self._api.get_device_state(self._device["_id"])
        if not state:
            return

        self._device["state"] = state["state"]
        self.async_write_ha_state()


class NTCTemperatureSensor(SensorEntity):
    """Sensor for a specific NTC temperature probe."""

    def __init__(self, api: Any, device: dict[str, Any], ntc_index: int, ctn_type: str) -> None:
        """Initialize the NTC temperature sensor.

        Args:
            api: The API client used to interact with the device.
            device: The device information containing name, ID, and state.
            ntc_index: The index of the NTC temperature probe.
            ctn_type: The type of the CTN sensor.

        """
        self._api = api
        self._device = device
        self._parents = parents_to_dict(device["parents"]) if "parents" in device else {}
        self._ntc_index = ntc_index
        self._ctn_type = ctn_type
        self._attr_name = f"MyNeo {device['name']} {CtnType.get_label(ctn_type)} Temp {ntc_index}"
        self._attr_unique_id = f"myneo_{device['_id']}_ntc{ntc_index}"
        self._attr_device_class = "temperature"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_should_poll = True

    @property
    def native_value(self) -> float | None:
        """Return the current temperature value or None if invalid."""
        temp = self._device["state"].get(f"ntc{self._ntc_index}Temp")
        return temp if temp > -50 else None

    async def async_update(self) -> None:
        """Fetch the latest state of the NTC temperature sensor.

        This method retrieves the current state of the device from the API
        and updates the sensor's state in Home Assistant.
        """
        response = await self._api.get_sub_device_state(self._parents["gateway"])
        state = get_device_by_rfid(response, self._device["rfid"])
        if not state:
            return
        self._device["state"] = state["state"]
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensors from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The configuration entry.
        async_add_entities (AddEntitiesCallback): Callback to add entities.

    """
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data["devices"]

    options = dict(config_entry.options)
    updated = False

    added_ids = set()
    entities_by_id: dict[str, list[SensorEntity]] = {}

    def _create_entities(device: dict) -> list[SensorEntity]:
        entities = []
        state = device.get("state", {})
        uid = device["_id"]
        added_ids.add(uid)

        # Energy sensor
        if "consumption" in state:
            key = f"{uid}_offset"
            current_value = round(state["consumption"] / 1000, 3)
            base_offset = float(options.get(key, current_value))

            if key not in options:
                options[key] = base_offset
                nonlocal updated
                updated = True

            entities.append(DevicesEnergySensor(api, device, base_offset))

        # NTC sensors
        if "ctnType" in state:
            ctn_sensors = Sensors.from_number(state["ctnType"])
            for index, ctn_type in enumerate([ctn_sensors.ctn0, ctn_sensors.ctn1, ctn_sensors.ctn2]):
                temp_key = f"ntc{index}Temp"
                if temp_key in state:
                    entities.append(NTCTemperatureSensor(api, device, index, ctn_type))

        if entities:
            entities_by_id[f"myneo_{uid}"] = entities
        return entities

    initial_entities = []
    for device in devices:
        initial_entities.extend(_create_entities(device))

    async_add_entities(initial_entities)

    if updated:
        hass.config_entries.async_update_entry(
            config_entry,
            options=options,
        )

    async def add_new_entity(device: dict) -> None:
        if device["_id"] in added_ids:
            return
        new_entities = _create_entities(device)
        if new_entities:
            _LOGGER.info("MyNeomitis : Adding new sensor entity(ies) for %s", device.get("name"))
            async_add_entities(new_entities)

    async def remove_entity(device_id: str) -> None:
        uid = f"myneo_{device_id}"
        entities = entities_by_id.get(uid)
        if entities:
            _LOGGER.info("MyNeomitis : Removing sensor entity(ies): %s", uid)
            for entity in entities:
                await entity.async_remove()
            added_ids.discard(device_id)
            entities_by_id.pop(uid, None)

    api.register_discovery_callback(lambda dev: hass.async_create_task(add_new_entity(dev)))
    api.register_removal_callback(lambda dev_id: hass.async_create_task(remove_entity(dev_id)))

