import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_USERNAME

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import AnkiDataUpdateCoordinator

logger = logging.getLogger(__name__)


class AnkiSensor(SensorEntity):
    def __init__(self, coordinator, field):
        self.coordinator = coordinator
        self.field = field

    @property
    def name(self):
        return f"Anki {self.field} cards"

    @property
    def state(self):
        return self.coordinator.data[self.field] if self.coordinator.data else None

    @property
    def unique_id(self):
        return (
            self.coordinator.config[CONF_USERNAME]
            + (
                "_" + self.coordinator.config[CONF_HOST]
                if self.coordinator.config[CONF_HOST] != DEFAULT_HOST
                else ""
            )
            + "_"
            + self.field
        )


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
):
    coordinator = AnkiDataUpdateCoordinator(hass, entry.data)
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Create sensors
    async_add_entities(
        AnkiSensor(coordinator, field) for field in ("new", "learn", "review")
    )
