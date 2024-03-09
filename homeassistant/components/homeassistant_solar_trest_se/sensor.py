from homeassistant.components.sensor import SensorEntity  # noqa: D100
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrestDataCoordinator
from .domain.solar_history import SolarHistory


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an Epion entry."""
    coordinator: TrestDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [TrestSolarControllerSensor(coordinator)]

    async_add_entities(entities)


class TrestSolarControllerSensor(CoordinatorEntity[TrestDataCoordinator], SensorEntity):
    """The sensor for Trest Solar Controller."""

    def __init__(self, coordinator: TrestDataCoordinator) -> None:
        """TrestSolarControllerSensor constructor."""

        super().__init__(coordinator)
        self.solar_history: SolarHistory
