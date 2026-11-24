"""Support for the read-only image setting sensors of Hikvision cameras."""

from dataclasses import dataclass
from typing import override

from pyhik.image import ImageSetting, ImageSettingType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import IMAGE_SELECT_SETTINGS, IMAGE_SWITCH_SETTINGS
from .coordinator import HikvisionImageCoordinator
from .entity import HikvisionImageChoiceEntity, image_option_map

# The sensors only read the values the coordinator already polls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HikvisionSensorEntityDescription(SensorEntityDescription):
    """Describes a Hikvision image setting sensor."""

    # Matched case-insensitively: some firmware spells the same path differently.
    path: str
    # As for the select: the camera's value as a translated option, or as it is.
    translate_options: bool = True


# A setting with a single choice cannot be changed, so it gets no select, nor
# a switch for a flag the camera offers only one value of. It is still worth
# reading, so it is shown by a sensor named like the select or switch would be.
SENSOR_DESCRIPTIONS: tuple[HikvisionSensorEntityDescription, ...] = (
    *(
        HikvisionSensorEntityDescription(
            key=setting.key,
            translation_key=setting.key,
            path=setting.path,
            translate_options=setting.translate_options,
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
        for setting in IMAGE_SELECT_SETTINGS
    ),
    *(
        HikvisionSensorEntityDescription(
            key=setting.key,
            translation_key=setting.key,
            path=setting.path,
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
        for setting in IMAGE_SWITCH_SETTINGS
        # A flag that is a select too has its sensor already.
        if setting.path.lower()
        not in {select.path.lower() for select in IMAGE_SELECT_SETTINGS}
    ),
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
    coordinator = entry.runtime_data.image_coordinator
    if coordinator is None:
        return

    entities: list[HikvisionImageSensor] = []
    for setting in coordinator.settings:
        if setting.type is not ImageSettingType.SELECT or len(setting.options) != 1:
            # A setting with several choices is a select.
            continue
        if (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower())) is None:
            continue
        if (
            options := image_option_map(setting, description.translate_options)
        ) is None:
            continue
        entities.append(
            HikvisionImageSensor(coordinator, entry, description, setting, options)
        )
    async_add_entities(entities)


class HikvisionImageSensor(HikvisionImageChoiceEntity, SensorEntity):
    """A read-only image setting that has a single choice.

    Shown like the select would show it: the same translated option, and the off
    option of a linked mode while its feature is off.
    """

    entity_description: HikvisionSensorEntityDescription

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: HikvisionSensorEntityDescription,
        setting: ImageSetting,
        options: dict[str, str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, description, setting, options)
        self._attr_options = list(options)

    @property
    @override
    def native_value(self) -> str | None:
        """Return the option the camera reports, or None if it is not its choice.

        An enum sensor may only show one of its options.
        """
        return self._current_option
