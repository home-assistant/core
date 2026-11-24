"""Support for the image setting selects of Hikvision cameras."""

from dataclasses import dataclass
import logging
from typing import override

from pyhik.image import ImageSetting, ImageSettingType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import IMAGE_SELECT_SETTINGS
from .coordinator import HikvisionImageCoordinator
from .entity import HikvisionImageChoiceEntity, image_option_map

_LOGGER = logging.getLogger(__name__)

# All writes to a camera are serialized by the coordinator.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HikvisionSelectEntityDescription(SelectEntityDescription):
    """Describes a Hikvision image setting select."""

    path: str
    translate_options: bool = True


SELECT_DESCRIPTIONS: tuple[HikvisionSelectEntityDescription, ...] = tuple(
    HikvisionSelectEntityDescription(
        key=setting.key,
        translation_key=setting.key,
        path=setting.path,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=setting.enabled_by_default,
        translate_options=setting.translate_options,
    )
    for setting in IMAGE_SELECT_SETTINGS
)

_DESCRIPTIONS_BY_PATH = {
    description.path.lower(): description for description in SELECT_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hikvision image setting selects."""
    entities: list[HikvisionImageSelect] = []
    for coordinator in entry.runtime_data.image_coordinators:
        for setting in coordinator.settings:
            if setting.type is not ImageSettingType.SELECT or len(setting.options) < 2:
                # A setting with a single choice cannot be changed.
                continue
            if (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower())) is None:
                continue
            if (
                options := image_option_map(setting, description.translate_options)
            ) is None:
                _LOGGER.debug(
                    "Skipping %s: its options %s cannot be told apart",
                    setting.path,
                    setting.options,
                )
                continue
            entities.append(
                HikvisionImageSelect(coordinator, entry, description, setting, options)
            )
    async_add_entities(entities)


class HikvisionImageSelect(HikvisionImageChoiceEntity, SelectEntity):
    """A select for an image setting with a list of choices."""

    entity_description: HikvisionSelectEntityDescription

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: HikvisionSelectEntityDescription,
        setting: ImageSetting,
        options: dict[str, str],
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, entry, description, setting, options)
        self._attr_options = list(options)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._current_option

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the option."""
        value = self._value_by_option[option]
        if self._setting.linked_enabled_path is not None:
            await self.coordinator.async_set_linked_setting(
                self._setting, value, self._context
            )
        else:
            await self.coordinator.async_set_setting(self._path, value, self._context)
