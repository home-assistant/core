"""Number support for Bravia TV."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BraviaTVConfigEntry, BraviaTVCoordinator
from .entity import BraviaTVEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BraviaTVNumberDescription(NumberEntityDescription):
    """Bravia TV Number description."""

    get_value_fn: Callable[[BraviaTVCoordinator], int | None]
    set_value_fn: Callable[[BraviaTVCoordinator, int], Coroutine[Any, Any, None]]
    supported_fn: Callable[[BraviaTVCoordinator], bool]


def _get_picture_setting_value(
    coordinator: BraviaTVCoordinator, target: str
) -> int | None:
    """Get picture setting value."""
    if not coordinator.picture_settings:
        return None
    for setting in coordinator.picture_settings:
        if setting.get("target") == target:
            return int(setting.get("currentValue", 0))
    return None


def _is_picture_setting_supported(
    coordinator: BraviaTVCoordinator, target: str
) -> bool:
    """Check if picture setting is supported."""
    if not coordinator.picture_settings:
        return False
    return any(
        setting.get("target") == target for setting in coordinator.picture_settings
    )


async def _set_picture_setting(
    coordinator: BraviaTVCoordinator, target: str, value: int
) -> None:
    """Set picture setting value."""
    await coordinator.async_set_picture_setting(target, str(value))


NUMBERS: tuple[BraviaTVNumberDescription, ...] = (
    BraviaTVNumberDescription(
        key="brightness",
        translation_key="brightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "brightness"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "brightness", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "brightness"
        ),
    ),
    BraviaTVNumberDescription(
        key="contrast",
        translation_key="contrast",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "contrast"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "contrast", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "contrast"
        ),
    ),
    BraviaTVNumberDescription(
        key="color",
        translation_key="color",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "color"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "color", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "color"
        ),
    ),
    BraviaTVNumberDescription(
        key="sharpness",
        translation_key="sharpness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "sharpness"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "sharpness", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "sharpness"
        ),
    ),
    BraviaTVNumberDescription(
        key="color_temperature",
        translation_key="color_temperature",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "colorTemperature"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "colorTemperature", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "colorTemperature"
        ),
    ),
    BraviaTVNumberDescription(
        key="picture_mode",
        translation_key="picture_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "pictureMode"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "pictureMode", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "pictureMode"
        ),
    ),
    BraviaTVNumberDescription(
        key="color_space",
        translation_key="color_space",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "colorSpace"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "colorSpace", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "colorSpace"
        ),
    ),
    BraviaTVNumberDescription(
        key="light_sensor",
        translation_key="light_sensor",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "lightSensor"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "lightSensor", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "lightSensor"
        ),
    ),
    BraviaTVNumberDescription(
        key="auto_picture_mode",
        translation_key="auto_picture_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "autoPictureMode"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "autoPictureMode", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "autoPictureMode"
        ),
    ),
    BraviaTVNumberDescription(
        key="hdr_mode",
        translation_key="hdr_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "hdrMode"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "hdrMode", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "hdrMode"
        ),
    ),
    BraviaTVNumberDescription(
        key="auto_local_dimming",
        translation_key="auto_local_dimming",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "autoLocalDimming"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "autoLocalDimming", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "autoLocalDimming"
        ),
    ),
    BraviaTVNumberDescription(
        key="xtended_dynamic_range",
        translation_key="xtended_dynamic_range",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        get_value_fn=lambda coordinator: _get_picture_setting_value(
            coordinator, "xtendedDynamicRange"
        ),
        set_value_fn=lambda coordinator, value: _set_picture_setting(
            coordinator, "xtendedDynamicRange", value
        ),
        supported_fn=lambda coordinator: _is_picture_setting_supported(
            coordinator, "xtendedDynamicRange"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bravia TV Number entities."""
    coordinator = config_entry.runtime_data
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        BraviaTVNumber(coordinator, unique_id, description)
        for description in NUMBERS
        if description.supported_fn(coordinator)
    )


class BraviaTVNumber(BraviaTVEntity, NumberEntity):
    """Representation of a Bravia TV Number."""

    entity_description: BraviaTVNumberDescription

    def __init__(
        self,
        coordinator: BraviaTVCoordinator,
        unique_id: str,
        description: BraviaTVNumberDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, unique_id)
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self.entity_description = description
        # Initialize with defaults from entity description
        self._attr_native_min_value = description.native_min_value or 0
        self._attr_native_max_value = description.native_max_value or 100
        self._attr_native_step = description.native_step or 1
        # Update with dynamic values from API
        self._update_dynamic_attributes()

    def _update_dynamic_attributes(self) -> None:
        """Update min/max/step from API data."""
        if not self.coordinator.picture_settings:
            return

        # Find the setting for this entity
        target_key = self.entity_description.key
        # Map entity key to API target name
        target_map = {
            "brightness": "brightness",
            "contrast": "contrast",
            "color": "color",
            "sharpness": "sharpness",
            "color_temperature": "colorTemperature",
            "picture_mode": "pictureMode",
            "color_space": "colorSpace",
            "light_sensor": "lightSensor",
            "auto_picture_mode": "autoPictureMode",
            "hdr_mode": "hdrMode",
            "auto_local_dimming": "autoLocalDimming",
            "xtended_dynamic_range": "xtendedDynamicRange",
        }
        target = target_map.get(target_key, target_key)

        for setting in self.coordinator.picture_settings:
            if setting.get("target") == target:
                # Get candidate info (min/max/step)
                candidates = setting.get("candidate", [])
                if candidates and isinstance(candidates[0], dict):
                    # Numeric setting with min/max/step
                    candidate = candidates[0]
                    self._attr_native_min_value = candidate.get("min", 0)
                    self._attr_native_max_value = candidate.get("max", 100)
                    self._attr_native_step = candidate.get("step", 1)
                break

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self.entity_description.get_value_fn(self.coordinator)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        self._update_dynamic_attributes()
        return self._attr_native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        self._update_dynamic_attributes()
        return self._attr_native_max_value

    @property
    def native_step(self) -> float:
        """Return the step value."""
        self._update_dynamic_attributes()
        return self._attr_native_step

    async def async_set_native_value(self, value: float) -> None:
        """Set the picture quality setting."""
        await self.entity_description.set_value_fn(self.coordinator, int(value))
