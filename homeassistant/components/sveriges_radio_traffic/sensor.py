"""Sensor for traffic information."""
from __future__ import annotations

import defusedxml.ElementTree as defET
import requests

# from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sr traffic platform."""
    async_add_entities([TrafficSensor()])


class TrafficSensor(SensorEntity):
    """A class for the Sveriges Radio traffic sensor."""

    _attr_has_entity_name = True
    _attr_name = "Sveriges Radio Traffic"
    _attr_state_class = None

    def __init__(self) -> None:
        """Initialize the sensor."""
        # do stuff
        self._attr_native_value = "Allt är kanon!"
        self._attr_auto_update = True
        self._attr_should_poll = True
        self.area = ""

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self._api_caller()

    def _api_caller(self) -> str:
        """Fetch stuff from SR-API."""
        response = requests.get("http://api.sr.se/api/v2/traffic/areas", timeout=10)
        tree = defET.fromstring(response.content)
        area_names = []
        for areas in tree.findall(".//areas"):
            for area in areas.findall(".//area"):
                area_names.append(area.attrib["name"])
        allAreasString = ", ".join(area_names)
        return allAreasString
