"""Support for Epson Workforce Printer."""
from __future__ import annotations

from datetime import timedelta

from epsonprinter_pkg.epsonprinterapi import EpsonPrinterAPI
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="black",
        name="Ink level Black",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="photoblack",
        name="Ink level Photoblack",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="magenta",
        name="Ink level Magenta",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="cyan",
        name="Ink level Cyan",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="yellow",
        name="Ink level Yellow",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="clean",
        name="Cleaning level",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
    ),
)
MONITORED_CONDITIONS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
    }
)
SCAN_INTERVAL = timedelta(minutes=60)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cartridge sensor."""
    host = config.get(CONF_HOST)

    api = EpsonPrinterAPI(host)
    if not api.available:
        raise PlatformNotReady()

    sensors = [
        EpsonPrinterCartridge(api, description)
        for description in SENSOR_TYPES
        if description.key in config[CONF_MONITORED_CONDITIONS]
    ]

    add_devices(sensors, True)


class EpsonPrinterCartridge(SensorEntity):
    """Representation of a cartridge sensor."""

    def __init__(
        self, api: EpsonPrinterAPI, description: SensorEntityDescription
    ) -> None:
        """Initialize a cartridge sensor."""
        self._api = api
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._api.getSensorValue(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self) -> None:
        """Get the latest data from the Epson printer."""
        self._api.update()
