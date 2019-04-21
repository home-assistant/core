"""Support for Toon binary sensors."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import (ToonEntity, ToonDisplayDeviceEntity, ToonBoilerDeviceEntity,
               ToonBoilerModuleDeviceEntity)
from .const import DATA_TOON_CLIENT, DOMAIN

DEPENDENCIES = ['toon']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(seconds=300)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up a Toon binary sensor based on a config entry."""
    toon = hass.data[DATA_TOON_CLIENT][entry.entry_id]

    sensors = [
        ToonBoilerModuleBinarySensor(toon, 'thermostat_info',
                                     'boiler_connected', None,
                                     'Boiler Module Connection',
                                     'mdi:check-network-outline',
                                     'connectivity'),

        ToonDisplayBinarySensor(toon, 'thermostat_info', 'active_state', 4,
                                "Toon Holiday Mode", 'mdi:airport', None),

        ToonDisplayBinarySensor(toon, 'thermostat_info', 'next_program', None,
                                "Toon Program", 'mdi:calendar-clock', None),
    ]

    if toon.thermostat_info.have_ot_boiler:
        sensors.extend([
            ToonBoilerBinarySensor(toon, 'thermostat_info',
                                   'ot_communication_error', '0',
                                   "OpenTherm Connection",
                                   'mdi:check-network-outline',
                                   'connectivity'),
            ToonBoilerBinarySensor(toon, 'thermostat_info', 'error_found', 255,
                                   "Boiler Status", 'mdi:alert', 'problem',
                                   inverted=True),
            ToonBoilerBinarySensor(toon, 'thermostat_info', 'burner_info',
                                   None, "Boiler Burner", 'mdi:fire', None),
            ToonBoilerBinarySensor(toon, 'thermostat_info', 'burner_info', '2',
                                   "Hot Tap Water", 'mdi:water-pump', None),
            ToonBoilerBinarySensor(toon, 'thermostat_info', 'burner_info', '3',
                                   "Boiler Preheating", 'mdi:fire', None),
        ])

    async_add_entities(sensors)


class ToonBinarySensor(ToonEntity, BinarySensorDevice):
    """Defines an Toon binary sensor."""

    def __init__(self, toon, section: str, measurement: str, on_value: Any,
                 name: str, icon: str, device_class: str,
                 inverted: bool = False) -> None:
        """Initialize the Toon sensor."""
        self._state = inverted
        self._device_class = device_class
        self.section = section
        self.measurement = measurement
        self.on_value = on_value
        self.inverted = inverted

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
            value = bool(max(0, int(self._state)))

        if self.inverted:
            return not value

        return value

    def update(self) -> None:
        """Get the latest data from the binary sensor."""
        section = getattr(self.toon, self.section)
        self._state = getattr(section, self.measurement)


class ToonBoilerBinarySensor(ToonBinarySensor, ToonBoilerDeviceEntity):
    """Defines a Boiler binary sensor."""

    pass


class ToonDisplayBinarySensor(ToonBinarySensor, ToonDisplayDeviceEntity):
    """Defines a Toon Display binary sensor."""

    pass


class ToonBoilerModuleBinarySensor(ToonBinarySensor,
                                   ToonBoilerModuleDeviceEntity):
    """Defines a Boiler module binary sensor."""

    pass
