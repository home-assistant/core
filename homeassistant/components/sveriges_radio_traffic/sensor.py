"""Sensor for traffic information."""
from __future__ import annotations

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

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self._api_caller()
        # self._attr_native_value = "Stockholm-Västerås. Risk för förseningar. Reducerad spårkapacitet vid Bålsta."

    def _api_caller(self) -> str:
        return "It totally worked"
        # root = ET.fromstring(
        #    requests.get("http://api.sr.se/api/v2/traffic/areas", timeout=10).text
        # )
        # areas = [child.attrib["name"] for child in root[2]]
        # return ", ".join(areas)


# def setup_platform(
#   hass: HomeAssistant,
#   config: ConfigType,
#   add_entities: AddEntitiesCallback,
#   discovery_info: DiscoveryInfoType | None = None
# ) -> None:
#   """Set up the sensor platform."""
#   add_entities([ExampleSensor()])
#
# class ExampleSensor(SensorEntity):
#   """Representation of a Sensor."""
#   _attr_name = "Example Temperature"
#   _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
#   _attr_device_class = SensorDeviceClass.TEMPERATURE
#   _attr_state_class = SensorStateClass.MEASUREMENT
#   def update(self) -> None:
#       """Fetch new state data for the sensor.
#       This is the only method that should fetch new data for Home Assistant.
#       """
#       self._attr_native_value = 23
#
