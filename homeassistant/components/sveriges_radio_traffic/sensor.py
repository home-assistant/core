"""Sensor for traffic information."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import defusedxml.ElementTree as defET
import requests

from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AREA_NAME, DATE, DOMAIN, INFO

# dothis: Check trafikverket Train and try to do something similar. May be difficult/impossible to "dynamically" update location with sensor integration.
# Instead set it during initial set up.


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sr traffic platform."""
    # Add entry to trafficsensor constructor
    area = entry.data.get("area")
    titlename = entry.data.get("name")
    # print("Name i sensor:", name)
    names = INFO  # ["message", "time", "area"]
    async_add_entities(
        [TrafficSensor(hass, area, name, entry, titlename) for name in names]
    )


# Maybe need this maybe not?


class MySelect(SelectEntity):
    # Implement one of these methods.
    """A selector for selecting areas."""

    def __init__(self) -> None:
        """Init the stuff."""
        self._attr_current_option = "Örebro"
        self._attr_options = []

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""


class TrafficSensor(SensorEntity):
    """A class for the Sveriges Radio traffic sensor."""

    _attr_has_entity_name = True
    # _attr_name = "Message"
    _attr_device_class = None

    def __init__(
        self, hass: HomeAssistant | None, area, name, entry, titlename
    ) -> None:
        """Initialize the sensor."""
        # do stuff
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
        self.selector = MySelect()
        self._attr_icon = icon

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url="https://api.trafikinfo.trafikverket.se/",
            suggested_area="Sveriges Radio Traffic",
        )

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        # The stuff we send to the config entry is not saved in the config entry (After first setup)
        # domainsaver = self.hass.config_entries.async_entries(domain=DOMAIN)
        self.traffic_area = self.entry.data.get("area")
        self._attr_native_value = self._get_traffic_info()

    def _get_traffic_info(self) -> str | None:
        """Fetch traffic information from specific area."""
        # Obs! Below is dangerous if traffic_area isn't set, add security
        response = requests.get(
            "http://api.sr.se/api/v2/traffic/messages?trafficareaname="
            + self.traffic_area,
            timeout=10,
        )
        tree = defET.fromstring(response.content)
        return_string = ""
        if self._attr_name == CONF_AREA_NAME:
            return self.traffic_area

        for message in tree.findall(".//message"):
            return_string = message.find(self.api_name).text

        if self.api_name == DATE:
            (date, _, time) = return_string.partition("T")
            return_string = time[0:5] + ", " + date

        return return_string

    # If we are going with Trafikverket plan then this method is probably not needed
    def _get_traffic_areas(self) -> str:
        """Fetch all traffic areas from SR-API."""
        response = requests.get("http://api.sr.se/api/v2/traffic/areas", timeout=10)
        tree = defET.fromstring(response.content)
        area_names = []
        for areas in tree.findall(".//areas"):
            for area in areas.findall(".//area"):
                area_names.append(area.attrib["name"])
        allAreasString = ", ".join(area_names)
        return allAreasString

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes for Trafikverket Train sensor."""
        return None
