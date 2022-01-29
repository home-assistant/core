"""The FiveM sensor platform."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FiveMDataUpdateCoordinator, FiveMEntity
from .const import (
    ATTR_PLAYERS_LIST,
    ATTR_RESOURCES_LIST,
    DOMAIN,
    ICON_PLAYERS_MAX,
    ICON_PLAYERS_ONLINE,
    ICON_RESOURCES,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_RESOURCES,
    UNIT_PLAYERS_MAX,
    UNIT_PLAYERS_ONLINE,
    UNIT_RESOURCES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FiveM sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Create entities list.
    entities = [
        FiveMPlayersOnlineSensor(coordinator),
        FiveMPlayersMaxSensor(coordinator),
        FiveMResourcesSensor(coordinator),
    ]

    # Add sensor entities.
    async_add_entities(entities)


class FiveMSensorEntity(FiveMEntity, SensorEntity):
    """Representation of a FiveM sensor base entity."""

    def __init__(
        self,
        coordinator: FiveMDataUpdateCoordinator,
        type_name: str,
        icon: str,
        unit: str,
        device_class: str = None,
        extra_attrs: list[str] = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator, type_name, icon, device_class, extra_attrs)
        self._attr_native_unit_of_measurement = unit

    def _update_value(self):
        self._attr_native_value = self.coordinator.data[self.type_name]


class FiveMPlayersOnlineSensor(FiveMSensorEntity):
    """Representation of a FiveM online players sensor."""

    def __init__(self, coordinator: FiveMDataUpdateCoordinator) -> None:
        """Initialize online players sensor."""
        super().__init__(
            coordinator,
            NAME_PLAYERS_ONLINE,
            ICON_PLAYERS_ONLINE,
            UNIT_PLAYERS_ONLINE,
            extra_attrs=[ATTR_PLAYERS_LIST],
        )


class FiveMPlayersMaxSensor(FiveMSensorEntity):
    """Representation of a FiveM maximum number of players sensor."""

    def __init__(self, coordinator: FiveMDataUpdateCoordinator) -> None:
        """Initialize maximum number of players sensor."""
        super().__init__(
            coordinator, NAME_PLAYERS_MAX, ICON_PLAYERS_MAX, UNIT_PLAYERS_MAX
        )


class FiveMResourcesSensor(FiveMSensorEntity):
    """Representation of a FiveM resources sensor."""

    def __init__(self, coordinator: FiveMDataUpdateCoordinator) -> None:
        """Initialize resources sensor."""
        super().__init__(
            coordinator,
            NAME_RESOURCES,
            ICON_RESOURCES,
            UNIT_RESOURCES,
            extra_attrs=[ATTR_RESOURCES_LIST],
        )
