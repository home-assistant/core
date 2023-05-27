"""Support for EZVIZ select controls."""
from __future__ import annotations

from pyezviz.constants import SoundMode
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

SELECT_TYPES = SelectEntityDescription(
    key="alarm_sound_mod",
    name="Warning sound",
    icon="mdi:alarm",
    entity_category=EntityCategory.CONFIG,
    options=["soft", "intensive", "silent"],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ select entities based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizSensor(coordinator, camera, entity, SELECT_TYPES)
        for camera in coordinator.data
        for entity, value in coordinator.data[camera].items()
        if entity in SELECT_TYPES.key
        if value
    )


class EzvizSensor(EzvizEntity, SelectEntity):
    """Representation of a EZVIZ select entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        entity: str,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._sensor_name = entity
        self._attr_unique_id = f"{serial}_{entity}"
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        sound_mode_value = getattr(SoundMode, self.data[self._sensor_name]).value
        if sound_mode_value in [0, 1, 2]:
            return self.options[sound_mode_value]

        return None

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        sound_mode_value = self.options.index(option)

        try:
            self.coordinator.ezviz_client.alarm_sound(self._serial, sound_mode_value, 1)

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Cannot set Warning sound level for {self.name}"
            ) from err
