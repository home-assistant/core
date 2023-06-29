"""The FiveM sensor platform."""
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
from .entity import FiveMEntity, FiveMEntityDescription


@dataclass
class FiveMSensorEntityDescription(SensorEntityDescription, FiveMEntityDescription):
    """Describes FiveM sensor entity."""


SENSORS: tuple[FiveMSensorEntityDescription, ...] = (
    FiveMSensorEntityDescription(
        key=NAME_PLAYERS_MAX,
        translation_key="max_players",
        icon=ICON_PLAYERS_MAX,
        native_unit_of_measurement=UNIT_PLAYERS_MAX,
    ),
    FiveMSensorEntityDescription(
        key=NAME_PLAYERS_ONLINE,
        translation_key="online_players",
        icon=ICON_PLAYERS_ONLINE,
        native_unit_of_measurement=UNIT_PLAYERS_ONLINE,
        extra_attrs=[ATTR_PLAYERS_LIST],
    ),
    FiveMSensorEntityDescription(
        key=NAME_RESOURCES,
        translation_key="resources",
        icon=ICON_RESOURCES,
        native_unit_of_measurement=UNIT_RESOURCES,
        extra_attrs=[ATTR_RESOURCES_LIST],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FiveM sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Add sensor entities.
    async_add_entities(
        [FiveMSensorEntity(coordinator, description) for description in SENSORS]
    )


class FiveMSensorEntity(FiveMEntity, SensorEntity):
    """Representation of a FiveM sensor base entity."""

    entity_description: FiveMSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]
