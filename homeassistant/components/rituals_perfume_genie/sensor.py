"""Support for Rituals Perfume Genie sensors."""
from typing import Callable

from pyrituals import Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY, COORDINATORS, DEVICES, DOMAIN, HUB, ID, SENSORS
from .entity import DiffuserEntity

TITLE = "title"
ICON = "icon"
WIFI = "wific"
PERFUME = "rfidc"
FILL = "fillc"

PERFUME_NO_CARTRIDGE_ID = 19
FILL_NO_CARTRIDGE_ID = 12

BATTERY_SUFFIX = " Battery"
PERFUME_SUFFIX = " Perfume"
FILL_SUFFIX = " Fill"
WIFI_SUFFIX = " Wifi"

ATTR_SIGNAL_STRENGTH = "signal_strength"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up the diffuser sensors."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserPerfumeSensor(diffuser, coordinator))
        entities.append(DiffuserFillSensor(diffuser, coordinator))
        entities.append(DiffuserWifiSensor(diffuser, coordinator))
        if BATTERY in diffuser.data[HUB][SENSORS]:
            entities.append(DiffuserBatterySensor(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserPerfumeSensor(DiffuserEntity):
    """Representation of a diffuser perfume sensor."""

    def __init__(self, diffuser: Diffuser, coordinator: CoordinatorEntity) -> None:
        """Initialize the perfume sensor."""
        super().__init__(diffuser, coordinator, PERFUME_SUFFIX)

    @property
    def icon(self) -> str:
        """Return the perfume sensor icon."""
        if self.coordinator.data[HUB][SENSORS][PERFUME][ID] == PERFUME_NO_CARTRIDGE_ID:
            return "mdi:tag-remove"
        return "mdi:tag-text"

    @property
    def state(self) -> str:
        """Return the state of the perfume sensor."""
        return self.coordinator.data[HUB][SENSORS][PERFUME][TITLE]


class DiffuserFillSensor(DiffuserEntity):
    """Representation of a diffuser fill sensor."""

    def __init__(self, diffuser: Diffuser, coordinator: CoordinatorEntity) -> None:
        """Initialize the fill sensor."""
        super().__init__(diffuser, coordinator, FILL_SUFFIX)

    @property
    def icon(self) -> str:
        """Return the fill sensor icon."""
        if self.coordinator.data[HUB][SENSORS][FILL][ID] == FILL_NO_CARTRIDGE_ID:
            return "mdi:beaker-question"
        return "mdi:beaker"

    @property
    def state(self) -> str:
        """Return the state of the fill sensor."""
        return self.coordinator.data[HUB][SENSORS][FILL][TITLE]


class DiffuserBatterySensor(DiffuserEntity):
    """Representation of a diffuser battery sensor."""

    def __init__(self, diffuser: Diffuser, coordinator: CoordinatorEntity) -> None:
        """Initialize the battery sensor."""
        super().__init__(diffuser, coordinator, BATTERY_SUFFIX)

    @property
    def state(self) -> int:
        """Return the state of the battery sensor."""
        # Use ICON because TITLE may change in the future.
        # ICON filename does not match the image.
        return {
            "battery-charge.png": 100,
            "battery-full.png": 100,
            "Battery-75.png": 50,
            "battery-50.png": 25,
            "battery-low.png": 10,
        }[self.coordinator.data[HUB][SENSORS][BATTERY][ICON]]

    @property
    def device_class(self) -> str:
        """Return the class of the battery sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Return the battery unit of measurement."""
        return PERCENTAGE


class DiffuserWifiSensor(DiffuserEntity):
    """Representation of a diffuser wifi sensor."""

    def __init__(self, diffuser: Diffuser, coordinator: CoordinatorEntity) -> None:
        """Initialize the wifi sensor."""
        super().__init__(diffuser, coordinator, WIFI_SUFFIX)

    @property
    def state(self) -> int:
        """Return the state of the wifi sensor."""
        # Use ICON because TITLE may change in the future.
        return {
            "icon-signal.png": 100,
            "icon-signal-75.png": 70,
            "icon-signal-low.png": 25,
            "icon-signal-0.png": 0,
        }[self.coordinator.data[HUB][SENSORS][WIFI][ICON]]

    @property
    def device_class(self) -> str:
        """Return the class of the wifi sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def unit_of_measurement(self) -> str:
        """Return the wifi unit of measurement."""
        return PERCENTAGE
