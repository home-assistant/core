"""Support for Toon binary sensors."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import ToonEntity
from .const import DATA_TOON_CLIENT, DOMAIN

DEPENDENCIES = ['toon']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up a Toon binary sensor based on a config entry."""
    toon = hass.data[DATA_TOON_CLIENT][entry.entry_id]

    sensors = [
        ToonBinarySensor(toon, 'thermostat_info', 'burner_info', None,
                         "Boiler Burner", 'mdi:fire', None),
        ToonBinarySensor(toon, 'thermostat_info', 'burner_info', 2,
                         "Hot Tap Water", 'mdi:water-pump', None),
        ToonBinarySensor(toon, 'thermostat_info', 'active_state', 4,
                         "Toon Holiday Mode", 'mdi:airport', None),
    ]

    if toon.thermostat_info.have_ot_boiler:
        sensors.extend([
            ToonBinarySensor(toon, 'thermostat_info', 'ot_communication_error',
                             0, "OpenTherm Connection",
                             'mdi:check-network-outline', 'connectivity'),
            ToonBinarySensor(toon, 'thermostat_info', 'error_found', 255,
                             "Boiler Status", 'mdi:alert', 'problem'),
        ])

    async_add_entities(sensors)


class ToonBinarySensor(ToonEntity, BinarySensorDevice):
    """Define an Toon binary sensor."""

    def __init__(self, toon, section: str, measurement: str, on_value: Any,
                 name: str, icon: str, device_class: str) -> None:
        """Initialize the Toon sensor."""
        self._state = (device_class in ['connectivity', 'problem'])
        self._device_class = device_class
        self.section = section
        self.measurement = measurement
        self.on_value = on_value

        super().__init__(toon, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this binary sensor."""
        return '_'.join([DOMAIN, self.toon.agreement.id, 'binary_sensor',
                         self.section, self.measurement, str(self.on_value)])

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self._device_class

    @property
    def is_on(self) -> bool:
        """Return the status of the binary sensor."""
        if self.on_value is not None:
            value = self._state == self.on_value
        elif self._state is None:
            value = False
        else:
            value = bool(int(self._state))

        # Connectivity & Problems are reversed
        if self.device_class in ['connectivity', 'problem']:
            return not value

        return value

    async def async_update(self) -> None:
        """Get the latest data from the binary sensor."""
        section = getattr(self.toon, self.section)
        self._state = getattr(section, self.measurement)
