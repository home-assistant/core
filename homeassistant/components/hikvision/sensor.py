"""Support for the read-only image setting sensors of Hikvision cameras."""

from dataclasses import dataclass
from typing import override

from pyhik.image import ImageSettingType

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import IMAGE_SELECT_SETTINGS
from .coordinator import HikvisionImageCoordinator
from .entity import HikvisionImageEntity

# The sensors only read the values the coordinator already polls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HikvisionSensorEntityDescription(SensorEntityDescription):
    """Describes a Hikvision image setting sensor."""

    # Matched case-insensitively: some firmware spells the same path differently.
    path: str


# A setting with a single choice cannot be changed, so it gets no select. It is
# still worth reading, so it is shown by a sensor named like the select would be.
SENSOR_DESCRIPTIONS: tuple[HikvisionSensorEntityDescription, ...] = tuple(
    HikvisionSensorEntityDescription(
        key=setting.key,
        translation_key=setting.key,
        path=setting.path,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )
    for setting in IMAGE_SELECT_SETTINGS
)

_DESCRIPTIONS_BY_PATH = {
    description.path.lower(): description for description in SENSOR_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hikvision image setting sensors."""
    async_add_entities(
        HikvisionImageSensor(coordinator, entry, description)
        for coordinator in entry.runtime_data.image_coordinators
        for setting in coordinator.settings
        if setting.type is ImageSettingType.SELECT
        and len(setting.options) == 1
        and (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower()))
    )


class HikvisionImageSensor(HikvisionImageEntity, SensorEntity):
    """A read-only image setting that has a single choice."""

    entity_description: HikvisionSensorEntityDescription

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: HikvisionSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        # The path as the camera spells it, so that it finds the value.
        path = next(
            setting.path
            for setting in coordinator.settings
            if setting.path.lower() == description.path.lower()
        )
        super().__init__(coordinator, entry, path)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> str | None:
        """Return the value the camera reports."""
        return self._value
