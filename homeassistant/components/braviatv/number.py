"""Number support for Bravia TV."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
    is_numeric_setting,
    is_picture_setting_available,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BraviaTVNumberDescription(NumberEntityDescription):
    """Bravia TV Number description."""

    target: str  # The API target name (e.g., "brightness", "colorTemperature")
    get_value_fn: Callable[[PictureSettingsData], int | None]
    set_value_fn: Callable[[BraviaTVPictureCoordinator, int], Coroutine[Any, Any, None]]
    supported_fn: Callable[[PictureSettingsData], bool]
    available_fn: Callable[[PictureSettingsData], bool]


def _get_picture_setting_value(data: PictureSettingsData, target: str) -> int | None:
    """Get picture setting value as integer."""
    setting = get_picture_setting(data, target)
    if not setting:
        return None

    current_value = setting.get("currentValue")
    if current_value is None:
        return None

    # Only return value if it's numeric (int or numeric string)
    if isinstance(current_value, int):
        return current_value
    if isinstance(current_value, str):
        try:
            return int(current_value)
        except ValueError:
            # Non-numeric string value (e.g., enum like "dvBright")
            return None
    return None


def _is_numeric_picture_setting_supported(
    data: PictureSettingsData, target: str
) -> bool:
    """Check if picture setting is supported and is a numeric type."""
    setting = get_picture_setting(data, target)
    if not setting:
        return False

    # Check if setting is numeric (not an enum)
    return is_numeric_setting(setting)


def _create_number_description(
    key: str,
    target: str,
    translation_key: str,
    icon: str,
) -> BraviaTVNumberDescription:
    """Create a number entity description for a picture setting."""
    return BraviaTVNumberDescription(
        key=key,
        target=target,
        translation_key=translation_key,
        icon=icon,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=partial(_get_picture_setting_value, target=target),
        set_value_fn=partial(_set_picture_setting_with_target, target=target),
        supported_fn=partial(_is_numeric_picture_setting_supported, target=target),
        available_fn=partial(is_picture_setting_available, target=target),
    )


async def _set_picture_setting_with_target(
    coordinator: BraviaTVPictureCoordinator, value: int, *, target: str
) -> None:
    """Set picture setting value with target as keyword arg for partial."""
    await coordinator.async_set_picture_setting(target, str(value))


# Only include settings that are numeric (slider-type controls).
# Settings like pictureMode, colorSpace, hdrMode, colorTemperature are enums (string choices)
# and should be implemented as Select entities, not Number entities.
# Runtime filtering via _is_picture_setting_supported provides additional safety.
NUMBERS: tuple[BraviaTVNumberDescription, ...] = (
    _create_number_description(
        "brightness", "brightness", "brightness", "mdi:brightness-6"
    ),
    _create_number_description(
        "contrast", "contrast", "contrast", "mdi:contrast-circle"
    ),
    _create_number_description("color", "color", "color", "mdi:palette"),
    _create_number_description("sharpness", "sharpness", "sharpness", "mdi:image-edit"),
    _create_number_description("hue", "hue", "hue", "mdi:palette-outline"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bravia TV Number entities."""
    coordinator = config_entry.runtime_data.coordinator
    picture_coordinator = config_entry.runtime_data.picture_coordinator
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        BraviaTVNumber(coordinator, picture_coordinator, unique_id, description)
        for description in NUMBERS
        if description.supported_fn(picture_coordinator.data)
    )


class BraviaTVNumber(CoordinatorEntity[BraviaTVPictureCoordinator], NumberEntity):
    """Representation of a Bravia TV Number."""

    _attr_has_entity_name = True
    entity_description: BraviaTVNumberDescription

    def __init__(
        self,
        main_coordinator: BraviaTVCoordinator,
        picture_coordinator: BraviaTVPictureCoordinator,
        unique_id: str,
        description: BraviaTVNumberDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(picture_coordinator)
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self.entity_description = description
        self._attr_device_info = get_device_info(main_coordinator, unique_id)

        # Initialize with defaults from entity description
        self._attr_native_min_value = description.native_min_value or 0
        self._attr_native_max_value = description.native_max_value or 100
        self._attr_native_step = description.native_step or 1
        # Update with dynamic values from API
        self._update_dynamic_attributes()

    def _update_dynamic_attributes(self) -> None:
        """Update min/max/step from API data."""
        setting = get_picture_setting(
            self.coordinator.data, self.entity_description.target
        )
        if not setting:
            return

        # Get candidate info (min/max/step) per Sony API spec
        candidates = setting.get("candidate", [])
        if candidates and isinstance(candidates[0], dict):
            # Numeric setting with min/max/step
            candidate = candidates[0]
            self._attr_native_min_value = candidate.get("min", 0)
            self._attr_native_max_value = candidate.get("max", 100)
            self._attr_native_step = candidate.get("step", 1)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_dynamic_attributes()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check coordinator availability, TV power state, and Sony API isAvailable field
        if not super().available or not self.coordinator.is_on:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self.entity_description.get_value_fn(self.coordinator.data)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self._attr_native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self._attr_native_max_value

    @property
    def native_step(self) -> float:
        """Return the step value."""
        return self._attr_native_step

    async def async_set_native_value(self, value: float) -> None:
        """Set the picture quality setting."""
        await self.entity_description.set_value_fn(self.coordinator, int(value))
