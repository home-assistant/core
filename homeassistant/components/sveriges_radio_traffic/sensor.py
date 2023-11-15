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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

# dothis: Check trafikverket Train and try to do something similar. May be difficult/impossible to "dynamically" update location with sensor integration.
# Instead set it during initial set up.


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sr traffic platform."""
    area = entry.data.get("area")
    async_add_entities([TrafficSensor(hass, area)])


# async def async_update_entry()


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
    _attr_name = "Message"
    _attr_device_class = None

    def __init__(self, hass: HomeAssistant | None, area) -> None:
        """Initialize the sensor."""
        # do stuff
        self.thehass = hass
        self._attr_native_value = "No updates"
        self._attr_auto_update = True
        self._attr_should_poll = True
        self.traffic_area = area
        self._attr_unique_id = "05b972dcf28374406d13e879724bfe3b"
        self.selector = MySelect()
        # self.selector.options = self._get_traffic_areas().split(", ")

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        # The stuff we send to the config entry is not saved in the config entry (After first setup)
        domainsaver = self.hass.config_entries.async_entries(domain=DOMAIN)
        # print(len(domainsaver))
        self.traffic_area = domainsaver[0].data.get("area")
        # print(self.traffic_area)
        # Can't access selectors _attr (protected)
        # if not self.selector._attr_options:
        #     self.selector._attr_options = self._get_traffic_areas().split(", ")
        self._attr_native_value = self._get_traffic_info()

    def _get_traffic_info(self) -> str | None:
        """Fetch traffic information from specific area."""
        response = requests.get(
            "http://api.sr.se/api/v2/traffic/messages?trafficareaname="
            + self.traffic_area,
            timeout=10,
        )
        tree = defET.fromstring(response.content)
        descriptionReturn = ""

        for message in tree.findall(".//message"):
            # message.find("title").text
            descriptionReturn = message.find("description").text
            # message.find("exactlocation").text
            # message.find("createddate").text

            # msgs.append(description)
            # self._attr_native_value = description
            # msg_data = {"Road": title, "description": description, "location": location, "createddate": time}

            # msgs.append(msg_data)
            # test = ", ".join(msgs)

        return descriptionReturn

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
