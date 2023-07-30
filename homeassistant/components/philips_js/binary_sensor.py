"""Philips TV binary sensors."""
from __future__ import annotations

from haphilipsjs import PhilipsTV

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN


class PhilipsTVBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A entity description for Philips TV binary sensor."""

    def __init__(self, recording_entry, recording_value, *args, **kwargs) -> None:
        """Set up a binary sensor entity description and add additional attributes."""
        super().__init__(*args, **kwargs)
        self.recording_entry: str = recording_entry
        self.recording_value: str = recording_value


DESCRIPTIONS = (
    PhilipsTVBinarySensorEntityDescription(
        key="recording_ongoing",
        has_entity_name=True,
        translation_key="recording_ongoing",
        icon="mdi:record-rec",
        recording_entry="RecordingType",
        recording_value="RECORDING_ONGOING",
    ),
    PhilipsTVBinarySensorEntityDescription(
        key="recording_new",
        has_entity_name=True,
        translation_key="recording_new",
        icon="mdi:new-box",
        recording_entry="RecordingType",
        recording_value="RECORDING_NEW",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    if (
        coordinator.api.json_feature_supported("recordings", "List")
        and coordinator.api.api_version == 6
    ):
        async_add_entities(
            PhilipsTVBinarySensorEntityRecordingType(coordinator, description)
            for description in DESCRIPTIONS
        )


def _check_for_recording_entry(api: PhilipsTV, entry: str, value: str) -> bool:
    """Return True if at least one specified value is available within entry of list."""
    for rec in api.recordings_list["recordings"]:
        if rec[entry] == value:
            return True
    return False


class PhilipsTVBinarySensorEntityRecordingType(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], BinarySensorEntity
):
    """A Philips TV binary sensor class, which allows multiple entities given by a BinarySensorEntityDescription."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        description: PhilipsTVBinarySensorEntityDescription,
    ) -> None:
        """Initialize entity class."""
        self.coordinator = coordinator
        self.description = description

        self.entity_description = self.description
        self._attr_unique_id = f"{self.coordinator.unique_id}_{self.description.key}"
        self._attr_device_info = self.coordinator.device_info

        super().__init__(coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and set is_on true if one specified value is available within given entry of list."""
        self._attr_is_on = _check_for_recording_entry(
            self.coordinator.api,
            self.description.recording_entry,
            self.description.recording_value,
        )
        super()._handle_coordinator_update()
