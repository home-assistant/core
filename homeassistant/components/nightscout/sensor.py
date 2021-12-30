"""Support for Nightscout sensors."""
from __future__ import annotations

from asyncio import TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DATE, ENTITY_CATEGORY_DIAGNOSTIC, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_BATTERY_VOLTAGE,
    ATTR_DELTA,
    ATTR_DEVICE,
    ATTR_DIRECTION,
    ATTR_TYPE,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Blood Glucose"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""
    api = hass.data[DOMAIN][entry.entry_id]

    # Glucose sensor
    async_add_entities([NightscoutSensor(api, "Blood Sugar", entry.unique_id)], True)

    # Uploader batteries
    async def async_update_batteries():
        """Fetch the latest data from Nightscout REST API and update the state of devices batteries."""
        try:
            return await api.get_latest_devices_status()
        except OSError as error:
            _LOGGER.error(
                "Error fetching battery devices status. Failed with %s", error
            )
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="battery_sensor",
        update_method=async_update_batteries,
        update_interval=timedelta(minutes=5),
    )

    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        Battery(coordinator, api, device_name, f"{entry.unique_id}_{device_name}")
        for device_name in coordinator.data
    )


class NightscoutSensor(SensorEntity):
    """Implementation of a Nightscout sensor."""

    def __init__(self, api: NightscoutAPI, name, unique_id):
        """Initialize the Nightscout sensor."""
        self.api = api
        self._unique_id = unique_id
        self._name = name
        self._state = None
        self._attributes = None
        self._unit_of_measurement = "mg/dL"
        self._icon = "mdi:cloud-question"
        self._available = False

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self._available

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    async def async_update(self):
        """Fetch the latest data from Nightscout REST API and update the state."""
        try:
            values = await self.api.get_sgvs()
        except (ClientError, AsyncIOTimeoutError, OSError) as error:
            _LOGGER.error("Error fetching data. Failed with %s", error)
            self._available = False
            return

        self._available = True
        self._attributes = {}
        self._state = None
        if values:
            value = values[0]
            self._attributes = {
                ATTR_DEVICE: value.device,
                ATTR_DATE: value.date,
                ATTR_DELTA: value.delta,
                ATTR_DIRECTION: value.direction,
            }
            self._state = value.sgv
            self._icon = self._parse_icon()
        else:
            self._available = False
            _LOGGER.warning("Empty reply found when expecting JSON data")

    def _parse_icon(self) -> str:
        """Update the icon based on the direction attribute."""
        switcher = {
            "Flat": "mdi:arrow-right",
            "SingleDown": "mdi:arrow-down",
            "FortyFiveDown": "mdi:arrow-bottom-right",
            "DoubleDown": "mdi:chevron-triple-down",
            "SingleUp": "mdi:arrow-up",
            "FortyFiveUp": "mdi:arrow-top-right",
            "DoubleUp": "mdi:chevron-triple-up",
        }
        return switcher.get(self._attributes[ATTR_DIRECTION], "mdi:cloud-question")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class Battery(CoordinatorEntity, SensorEntity):
    """Battery sensor of Nightscout device."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    def __init__(self, coordinator, api: NightscoutAPI, name, unique_id):
        """Initialize the Nightscout sensor."""
        super().__init__(coordinator)
        self.api = api
        self._unique_id = unique_id
        self._name = name
        self._device_name = name
        self._icon = "mdi:battery-unknown"

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return if the sensor data are available."""
        return hasattr(self.coordinator.data[self._name], "uploader")

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.coordinator.data[self._name].uploader.battery

    @property
    def icon(self) -> str:
        """Battery state icon handling."""
        return icon_for_battery_level(
            battery_level=self.coordinator.data[self._name].uploader.battery,
            charging=False,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        uploader = self.coordinator.data[self._name].uploader
        attr = {}
        if hasattr(uploader, "type"):
            attr[ATTR_TYPE] = uploader.type
        if hasattr(uploader, "batteryVoltage"):
            attr[ATTR_BATTERY_VOLTAGE] = uploader.batteryVoltage
        return attr
