"""Sensor for traffic information from Sveriges Radio."""
from __future__ import annotations

import defusedxml.ElementTree as defET
import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AREA_NAME, DATE, DOMAIN, INFO


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sveriges Radio traffic platform."""
    # Add entry to trafficsensor constructor
    area = entry.data.get("area")
    titlename = entry.data.get("name")
    names = INFO
    async_add_entities(
        [TrafficSensor(hass, area, name, entry, titlename) for name in names]
    )


class TrafficSensor(SensorEntity):
    """A class for the Sveriges Radio traffic sensor."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self, hass: HomeAssistant | None, area, name, entry, titlename
    ) -> None:
        """Initialize the sensor."""
        self.entry = entry
        api_name, description_name, icon = name
        self.thehass = hass
        self._attr_name = description_name
        self.api_name = api_name
        self._attr_native_value = (
            area if description_name == CONF_AREA_NAME else "No updates"
        )
        self._attr_auto_update = True
        self._attr_should_poll = True
        self.traffic_area = area
        self._attr_unique_id = f"05b972dcf28374406d13e879724bfe3b{name}"
        self._attr_icon = icon

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url="https://sverigesradio.se/oppetapi",
        )

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.traffic_area = self.entry.data.get("area")
        self._attr_native_value = self._get_traffic_info()

    def _get_traffic_info(self) -> str | None:
        """Fetch traffic information from specific area."""

        # Safeguard for API call
        if not self.traffic_area:
            return "Invalid traffic area"

        # Traffic area is stored locally, no need to fetch from API response
        if self._attr_name == CONF_AREA_NAME:
            return self.traffic_area

        # API call
        response = requests.get(
            "https://api.sr.se/api/v2/traffic/messages?trafficareaname="
            + self.traffic_area,
            timeout=10,
        )
        tree = defET.fromstring(response.content)
        return_string = ""

        # Find the latest traffic message
        for message in tree.findall(".//message"):
            return_string = message.find(self.api_name).text

        # Format date to more readable version
        if self.api_name == DATE:
            (date, _, time) = return_string.partition("T")
            return_string = time[0:5] + ", " + date

        return return_string
