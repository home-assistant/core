"""Support for EZVIZ select controls."""

from __future__ import annotations

from dataclasses import dataclass

from pyezviz.constants import DeviceSwitchType, SoundMode
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EzvizSelectEntityDescription(SelectEntityDescription):
    """Describe a EZVIZ Select entity."""

    supported_switch: int


SELECT_TYPE = EzvizSelectEntityDescription(
    key="alarm_sound_mod",
    translation_key="alarm_sound_mode",
    entity_category=EntityCategory.CONFIG,
    options=["soft", "intensive", "silent"],
    supported_switch=DeviceSwitchType.ALARM_TONE.value,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ select entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        EzvizSelect(coordinator, camera)
        for camera in coordinator.data
        for switch in coordinator.data[camera]["switches"]
        if switch == SELECT_TYPE.supported_switch
    )


class EzvizSelect(EzvizEntity, SelectEntity):
    """Representation of a EZVIZ select entity."""

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{SELECT_TYPE.key}"
        self.entity_description = SELECT_TYPE

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        sound_mode_value = getattr(
            SoundMode, self.data[self.entity_description.key]
        ).value
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
                f"Cannot set Warning sound level for {self.entity_id}"
            ) from err
