"""Philips TV binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from haphilipsjs import PhilipsTV

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN
from .entity import PhilipsJsEntity


@dataclass(frozen=True, kw_only=True)
class PhilipsTVBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A entity description for Philips TV binary sensor."""

    recording_value: str


DESCRIPTIONS = (
    PhilipsTVBinarySensorEntityDescription(
        key="recording_ongoing",
        translation_key="recording_ongoing",
        recording_value="RECORDING_ONGOING",
    ),
    PhilipsTVBinarySensorEntityDescription(
        key="recording_new",
        translation_key="recording_new",
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
    if api.recordings_list is None:
        return False
    return any(rec.get(entry) == value for rec in api.recordings_list["recordings"])


class PhilipsTVBinarySensorEntityRecordingType(PhilipsJsEntity, BinarySensorEntity):
    """A Philips TV binary sensor class, which allows multiple entities given by a BinarySensorEntityDescription."""

    entity_description: PhilipsTVBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        description: PhilipsTVBinarySensorEntityDescription,
    ) -> None:
        """Initialize entity class."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_is_on = _check_for_recording_entry(
            coordinator.api,
            "RecordingType",
            description.recording_value,
        )

        super().__init__(coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and set is_on true if one specified value is available within given entry of list."""
        self._attr_is_on = _check_for_recording_entry(
            self.coordinator.api,
            "RecordingType",
            self.entity_description.recording_value,
        )
        super()._handle_coordinator_update()
