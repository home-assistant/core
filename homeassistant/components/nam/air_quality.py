"""Support for the Nettigo Air Monitor air_quality service."""
from __future__ import annotations

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NAMDataUpdateCoordinator
from .const import AIR_QUALITY_SENSORS, DEFAULT_NAME, DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for sensor in AIR_QUALITY_SENSORS:
        if f"{sensor}_p1" in coordinator.data:
            entities.append(NAMAirQuality(coordinator, sensor))

    async_add_entities(entities, False)


class NAMAirQuality(CoordinatorEntity, AirQualityEntity):
    """Define an Nettigo Air Monitor air quality."""

    coordinator: NAMDataUpdateCoordinator

    def __init__(self, coordinator: NAMDataUpdateCoordinator, sensor_type: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{DEFAULT_NAME} {AIR_QUALITY_SENSORS[self.sensor_type]}"

    @property
    def particulate_matter_2_5(self) -> StateType:
        """Return the particulate matter 2.5 level."""
        return round_state(getattr(self.coordinator.data, f"{self.sensor_type}_p2"))

    @property
    def particulate_matter_10(self) -> StateType:
        """Return the particulate matter 10 level."""
        return round_state(getattr(self.coordinator.data, f"{self.sensor_type}_p1"))

    @property
    def carbon_dioxide(self) -> StateType:
        """Return the particulate matter 10 level."""
        return round_state(getattr(self.coordinator.data, "conc_co2_ppm", None))

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{self.coordinator.unique_id}-{self.sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return available and bool(
            getattr(self.coordinator.data, f"{self.sensor_type}_p2", None)
        )


def round_state(state: StateType) -> StateType:
    """Round state."""
    if isinstance(state, float):
        return round(state)

    return state
