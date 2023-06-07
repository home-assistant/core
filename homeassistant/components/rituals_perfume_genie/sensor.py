"""Support for Rituals Perfume Genie sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity

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
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[DiffuserEntity] = []
    for coordinator in coordinators.values():
        entities.extend(
            [
                DiffuserPerfumeSensor(coordinator),
                DiffuserFillSensor(coordinator),
                DiffuserWifiSensor(coordinator),
            ]
        )
        if coordinator.diffuser.has_battery:
            entities.append(DiffuserBatterySensor(coordinator))

    async_add_entities(entities)


class DiffuserPerfumeSensor(DiffuserEntity, SensorEntity):
    """Representation of a diffuser perfume sensor."""

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the perfume sensor."""
        super().__init__(coordinator, PERFUME_SUFFIX)

    @property
    def icon(self) -> str:
        """Return the perfume sensor icon."""
        if self.coordinator.diffuser.has_cartridge:
            return "mdi:tag-text"
        return "mdi:tag-remove"

    @property
    def native_value(self) -> str:
        """Return the state of the perfume sensor."""
        return self.coordinator.diffuser.perfume


class DiffuserFillSensor(DiffuserEntity, SensorEntity):
    """Representation of a diffuser fill sensor."""

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the fill sensor."""
        super().__init__(coordinator, FILL_SUFFIX)

    @property
    def icon(self) -> str:
        """Return the fill sensor icon."""
        if self.coordinator.diffuser.has_cartridge:
            return "mdi:beaker"
        return "mdi:beaker-question"

    @property
    def native_value(self) -> str:
        """Return the state of the fill sensor."""
        return self.coordinator.diffuser.fill


class DiffuserBatterySensor(DiffuserEntity, SensorEntity):
    """Representation of a diffuser battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, BATTERY_SUFFIX)

    @property
    def native_value(self) -> int:
        """Return the state of the battery sensor."""
        return self.coordinator.diffuser.battery_percentage


class DiffuserWifiSensor(DiffuserEntity, SensorEntity):
    """Representation of a diffuser wifi sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the wifi sensor."""
        super().__init__(coordinator, WIFI_SUFFIX)

    @property
    def native_value(self) -> int:
        """Return the state of the wifi sensor."""
        return self.coordinator.diffuser.wifi_percentage
