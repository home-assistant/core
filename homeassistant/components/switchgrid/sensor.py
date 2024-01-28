from homeassistant.components.sensor import DEVICE_CLASS_TIMESTAMP, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchgridCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator: SwitchgridCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            SwitchgridNextEventSensor(
                coordinator,
            )
        ]
    )


class SwitchgridNextEventSensor(CoordinatorEntity[SwitchgridCoordinator], SensorEntity):
    """Sensor to show single grid specific values."""

    _attr_unique_id = "switchgrid_next_event"
    _attr_has_entity_name = True
    _attr_translation_key = "switchgrid_next_event"
    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    def __init__(
        self,
        coordinator: SwitchgridCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)

    @property
    def native_value(self) -> str | None:
        """Return the value of the sensor."""
        return self.coordinator.next_event()["startUtc"]
