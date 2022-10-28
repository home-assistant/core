"""Support for Epic Games Store sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EGSUpdateCoordinator

PARALLEL_UPDATES = 1

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="free_game_1",
        name="Free game 1",
    ),
    SensorEntityDescription(
        key="free_game_2",
        name="Free game 2",
    ),
    SensorEntityDescription(
        key="next_free_game_1",
        name="Next free game 1",
    ),
    SensorEntityDescription(
        key="next_free_game_2",
        name="Next free game 2",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Epic Games Store sensors based on a config entry."""
    coordinator: EGSUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [EGSSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS],
        True,
    )


class EGSSensor(SensorEntity):
    """Representation of a Epic Games Store sensor."""

    def __init__(
        self,
        coordinator: EGSUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_unique_id = self.entity_description.key

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data[self.entity_description.key]["title"]
        return None

    @property
    def extra_state_attributes(self):
        """Return additional sensor state attributes."""
        if self.coordinator.data:
            return {
                "title": self.coordinator.data[self.entity_description.key]["title"],
                "publisher": self.coordinator.data[self.entity_description.key][
                    "publisher"
                ],
                "original_price": self.coordinator.data[self.entity_description.key][
                    "original_price"
                ],
                "url": self.coordinator.data[self.entity_description.key]["url"],
                "start_at": self.coordinator.data[self.entity_description.key][
                    "start_at"
                ],
                "end_at": self.coordinator.data[self.entity_description.key]["end_at"],
                "img_portrait": self.coordinator.data[self.entity_description.key][
                    "img_portrait"
                ],
                "img_landscape": self.coordinator.data[self.entity_description.key][
                    "img_landscape"
                ],
            }
        return {}
