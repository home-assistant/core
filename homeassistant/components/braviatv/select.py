"""Select support for Bravia TV."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    BraviaTVConfigEntry,
    BraviaTVCoordinator,
    BraviaTVPictureCoordinator,
)
from .entity import get_device_info
from .helpers import (
    PictureSettingsData,
    get_picture_setting,
    is_enum_setting,
    is_picture_setting_available,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BraviaTVSelectDescription(SelectEntityDescription):
    """Bravia TV Select description."""

    target: str  # The API target name (e.g., "pictureMode", "colorSpace")
    get_value_fn: Callable[[PictureSettingsData], str | None]
    get_options_fn: Callable[[PictureSettingsData], list[str]]
    set_value_fn: Callable[[BraviaTVPictureCoordinator, str], Coroutine[Any, Any, None]]
    supported_fn: Callable[[PictureSettingsData], bool]
    available_fn: Callable[[PictureSettingsData], bool]


def _get_picture_setting_value(data: PictureSettingsData, target: str) -> str | None:
    """Get picture setting value as string."""
    setting = get_picture_setting(data, target)
    if not setting:
        return None

    current_value = setting.get("currentValue")
    if current_value is None:
        return None

    # Return value as string
    return str(current_value)


def _get_picture_setting_options(data: PictureSettingsData, target: str) -> list[str]:
    """Get available options for an enum picture setting.

    Sony API returns candidates in two formats:
    - Simple strings: ["vivid", "standard", "cinema"]
    - Dict with value key: [{"value": "dvDark"}, {"value": "dvBright"}]
    """
    setting = get_picture_setting(data, target)
    if not setting:
        return []

    candidates = setting.get("candidate", [])
    if not candidates:
        return []

    first_candidate = candidates[0]

    # Simple string format
    if isinstance(first_candidate, str):
        return list(candidates)

    # Dict format with "value" key
    if isinstance(first_candidate, dict) and "value" in first_candidate:
        return [c["value"] for c in candidates if isinstance(c, dict) and "value" in c]

    return []


def _is_enum_picture_setting_supported(data: PictureSettingsData, target: str) -> bool:
    """Check if picture setting is supported and is an enum type."""
    setting = get_picture_setting(data, target)
    if not setting:
        return False

    # Check if setting is an enum (not numeric)
    return is_enum_setting(setting)


async def _set_picture_setting_with_target(
    coordinator: BraviaTVPictureCoordinator, value: str, *, target: str
) -> None:
    """Set picture setting value with target as keyword arg for partial."""
    await coordinator.async_set_picture_setting(target, value)


def _create_select_description(
    key: str,
    target: str,
    translation_key: str,
    icon: str,
) -> BraviaTVSelectDescription:
    """Create a select entity description for an enum picture setting."""
    return BraviaTVSelectDescription(
        key=key,
        target=target,
        translation_key=translation_key,
        icon=icon,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_value_fn=partial(_get_picture_setting_value, target=target),
        get_options_fn=partial(_get_picture_setting_options, target=target),
        set_value_fn=partial(_set_picture_setting_with_target, target=target),
        supported_fn=partial(_is_enum_picture_setting_supported, target=target),
        available_fn=partial(is_picture_setting_available, target=target),
    )


# Only include settings that are typically enums (dropdown/choice-type controls).
# Settings like brightness, contrast, color are numeric sliders
# and are implemented as Number entities.
# Runtime filtering via _is_picture_setting_supported provides additional safety.
SELECTS: tuple[BraviaTVSelectDescription, ...] = (
    _create_select_description(
        "picture_mode", "pictureMode", "picture_mode", "mdi:television-shimmer"
    ),
    _create_select_description(
        "color_space", "colorSpace", "color_space", "mdi:palette-outline"
    ),
    _create_select_description("hdr_mode", "hdrMode", "hdr_mode", "mdi:hdr"),
    _create_select_description(
        "light_sensor", "lightSensor", "light_sensor", "mdi:brightness-auto"
    ),
    _create_select_description(
        "auto_picture_mode",
        "autoPictureMode",
        "auto_picture_mode",
        "mdi:television-shimmer",
    ),
    _create_select_description(
        "auto_local_dimming",
        "autoLocalDimming",
        "auto_local_dimming",
        "mdi:brightness-auto",
    ),
    _create_select_description(
        "xtended_dynamic_range",
        "xtendedDynamicRange",
        "xtended_dynamic_range",
        "mdi:hdr",
    ),
    _create_select_description(
        "color_temperature",
        "colorTemperature",
        "color_temperature",
        "mdi:thermometer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bravia TV Select entities."""
    coordinator = config_entry.runtime_data.coordinator
    picture_coordinator = config_entry.runtime_data.picture_coordinator
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        BraviaTVSelect(coordinator, picture_coordinator, unique_id, description)
        for description in SELECTS
        if description.supported_fn(picture_coordinator.data)
    )


class BraviaTVSelect(CoordinatorEntity[BraviaTVPictureCoordinator], SelectEntity):
    """Representation of a Bravia TV Select."""

    _attr_has_entity_name = True
    entity_description: BraviaTVSelectDescription

    def __init__(
        self,
        main_coordinator: BraviaTVCoordinator,
        picture_coordinator: BraviaTVPictureCoordinator,
        unique_id: str,
        description: BraviaTVSelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(picture_coordinator)
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self.entity_description = description
        self._attr_device_info = get_device_info(main_coordinator, unique_id)

        # Initialize options from API data
        self._update_options()

    def _update_options(self) -> None:
        """Update available options from API data."""
        self._attr_options = self.entity_description.get_options_fn(
            self.coordinator.data
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_options()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check coordinator availability, TV power state, and Sony API isAvailable field
        if not super().available or not self.coordinator.is_on:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.get_value_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.coordinator, option)
