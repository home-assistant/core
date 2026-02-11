"""Support for Nightscout sensors."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DATE, UnitOfBloodGlucoseConcentration
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DELTA, ATTR_DEVICE, ATTR_DIRECTION, DOMAIN

SCAN_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Blood Glucose"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Glucose Sensor."""
    api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NightscoutSensor(api, "Blood Sugar", entry.unique_id)], True)


class NightscoutSensor(SensorEntity):
    """Implementation of a Nightscout sensor."""

    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION
    _attr_native_unit_of_measurement = (
        UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER
    )
    _attr_icon = "mdi:cloud-question"

    def __init__(self, api: NightscoutAPI, name: str, unique_id: str | None) -> None:
        """Initialize the Nightscout sensor."""
        self.api = api
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Fetch the latest data from Nightscout REST API and update the state."""
        try:
            values = await self.api.get_sgvs()
        except (ClientError, TimeoutError, OSError) as error:
            _LOGGER.error("Error fetching data. Failed with %s", error)
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_extra_state_attributes = {}
        self._attr_native_value = None
        if values:
            value = values[0]
            self._attr_extra_state_attributes = {
                ATTR_DEVICE: value.device,
                ATTR_DATE: value.date,
                ATTR_DELTA: value.delta,
                ATTR_DIRECTION: value.direction,
            }
            self._attr_native_value = value.sgv
            self._attr_icon = self._parse_icon(value.direction)
        else:
            self._attr_available = False
            _LOGGER.warning("Empty reply found when expecting JSON data")

    def _parse_icon(self, direction: str) -> str:
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
        return switcher.get(direction, "mdi:cloud-question")
