"""Support for Rituals Perfume Genie sensors."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN, SENSORS
from .entity import DiffuserEntity

ID = "id"
PERFUME = "rfidc"
FILL = "fillc"

PERFUME_NO_CARTRIDGE_ID = 19
FILL_NO_CARTRIDGE_ID = 12

BATTERY_SUFFIX = " Battery"
PERFUME_SUFFIX = " Perfume"
FILL_SUFFIX = " Fill"
WIFI_SUFFIX = " Wifi"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser sensors."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[DiffuserEntity] = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserPerfumeSensor(diffuser, coordinator))
        entities.append(DiffuserFillSensor(diffuser, coordinator))
        entities.append(DiffuserWifiSensor(diffuser, coordinator))
        if diffuser.has_battery:
            entities.append(DiffuserBatterySensor(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserPerfumeSensor(DiffuserEntity):
    """Representation of a diffuser perfume sensor."""

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the perfume sensor."""
        super().__init__(diffuser, coordinator, PERFUME_SUFFIX)

        self._attr_icon = "mdi:tag-text"
        if diffuser.hub_data[SENSORS][PERFUME][ID] == PERFUME_NO_CARTRIDGE_ID:
            self._attr_icon = "mdi:tag-remove"

    @property
    def state(self) -> str:
        """Return the state of the perfume sensor."""
        return self._diffuser.perfume


class DiffuserFillSensor(DiffuserEntity):
    """Representation of a diffuser fill sensor."""

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the fill sensor."""
        super().__init__(diffuser, coordinator, FILL_SUFFIX)

    @property
    def icon(self) -> str:
        """Return the fill sensor icon."""
        if self._diffuser.hub_data[SENSORS][FILL][ID] == FILL_NO_CARTRIDGE_ID:
            return "mdi:beaker-question"
        return "mdi:beaker"

    @property
    def state(self) -> str:
        """Return the state of the fill sensor."""
        return self._diffuser.fill


class DiffuserBatterySensor(DiffuserEntity):
    """Representation of a diffuser battery sensor."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_unit_of_measurement = PERCENTAGE

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(diffuser, coordinator, BATTERY_SUFFIX)

    @property
    def state(self) -> int:
        """Return the state of the battery sensor."""
        return self._diffuser.battery_percentage


class DiffuserWifiSensor(DiffuserEntity):
    """Representation of a diffuser wifi sensor."""

    _attr_device_class = DEVICE_CLASS_SIGNAL_STRENGTH
    _attr_unit_of_measurement = PERCENTAGE

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the wifi sensor."""
        super().__init__(diffuser, coordinator, WIFI_SUFFIX)

    @property
    def state(self) -> int:
        """Return the state of the wifi sensor."""
        return self._diffuser.wifi_percentage
