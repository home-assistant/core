"""Support for Epson Workforce Printer."""
from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from epsonprinter_pkg.epsonprinterapi import EpsonPrinterAPI
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS, PERCENTAGE
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv


class MonitoredConditionsMetadata(NamedTuple):
    """Metadata for an individual montiored condition."""

    name: str
    icon: str
    unit_of_measurement: str


MONITORED_CONDITIONS: dict[str, MonitoredConditionsMetadata] = {
    "black": MonitoredConditionsMetadata(
        "Ink level Black",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
    "photoblack": MonitoredConditionsMetadata(
        "Ink level Photoblack",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
    "magenta": MonitoredConditionsMetadata(
        "Ink level Magenta",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
    "cyan": MonitoredConditionsMetadata(
        "Ink level Cyan",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
    "yellow": MonitoredConditionsMetadata(
        "Ink level Yellow",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
    "clean": MonitoredConditionsMetadata(
        "Cleaning level",
        icon="mdi:water",
        unit_of_measurement=PERCENTAGE,
    ),
}
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
    }
)
SCAN_INTERVAL = timedelta(minutes=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the cartridge sensor."""
    host = config.get(CONF_HOST)

    api = EpsonPrinterAPI(host)
    if not api.available:
        raise PlatformNotReady()

    sensors = [
        EpsonPrinterCartridge(api, condition)
        for condition in config[CONF_MONITORED_CONDITIONS]
    ]

    add_devices(sensors, True)


class EpsonPrinterCartridge(SensorEntity):
    """Representation of a cartridge sensor."""

    def __init__(self, api, cartridgeidx):
        """Initialize a cartridge sensor."""
        self._api = api

        self._id = cartridgeidx
        metadata = MONITORED_CONDITIONS[self._id]
        self._attr_name = metadata.name
        self._attr_icon = metadata.icon
        self._attr_unit_of_measurement = metadata.unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._api.getSensorValue(self._id)

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data from the Epson printer."""
        self._api.update()
