"""Provides a sensor to track various OSC values."""

from typing import Optional, Union

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    osc_address = config_entry.data["osc_address"]
    config = hass.data[DOMAIN][osc_address]
    async_add_entities([OSCSensor(config, osc_address)])


class OSCSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_state_class = "measurement"

    def __init__(self, config: ConfigType, osc_address: str) -> None:
        """Initialize the sensor."""
        self._config = config
        self._osc_address = osc_address
        self._state: Optional[Union[int, float]]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._osc_address.replace("/", "_").lstrip("_")

    @property
    def unique_id(self) -> str:
        """Return the unique id of the sensor."""
        return self._osc_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="OSC",
        )

    def update(self) -> None:
        """Fetch new state data for this sensor."""
        self._attr_state = self.hass.data[DOMAIN][self._osc_address]["value"]
