"""Number support for Bravia TV."""

from typing import Any, override

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    NumberEntityDescription,
    RestoreNumber,
)
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


def _get_numeric_picture_setting(
    coordinator: BraviaTVPictureCoordinator, target: str
) -> dict[str, Any] | None:
    """Return the numeric picture setting for a target, if supported."""
    if (setting := coordinator.get_setting(target)) is None:
        return None
    # Numeric settings have a single candidate with a range, enum
    # settings have a candidate per allowed value.
    candidates = setting["candidate"]
    if not isinstance(candidates[0], dict) or "min" not in candidates[0]:
        return None
    return setting


NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="brightness",
        translation_key="brightness",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:brightness-6",
    ),
    NumberEntityDescription(
        key="color",
        translation_key="color",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:palette",
    ),
    NumberEntityDescription(
        key="contrast",
        translation_key="contrast",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:contrast-circle",
    ),
    NumberEntityDescription(
        key="hue",
        translation_key="hue",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:palette-outline",
    ),
    NumberEntityDescription(
        key="sharpness",
        translation_key="sharpness",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:image-edit",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bravia TV Number entities.

    Entities are added even if the TV is off, so the last state can be
    restored while waiting for the TV to come back.
    """

    coordinator = config_entry.runtime_data.coordinator
    picture_coordinator = config_entry.runtime_data.picture_coordinator
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        BraviaTVNumber(coordinator, picture_coordinator, unique_id, description)
        for description in NUMBERS
    )


class BraviaTVNumber(CoordinatorEntity[BraviaTVPictureCoordinator], RestoreNumber):
    """Representation of a Bravia TV Number."""

    _attr_has_entity_name = True
    entity_description: NumberEntityDescription

    def __init__(
        self,
        main_coordinator: BraviaTVCoordinator,
        picture_coordinator: BraviaTVPictureCoordinator,
        unique_id: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(picture_coordinator)
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = get_device_info(main_coordinator, unique_id)
        # Placeholders until the TV reports the actual range
        self._attr_native_min_value = DEFAULT_MIN_VALUE
        self._attr_native_max_value = DEFAULT_MAX_VALUE
        self._attr_native_step = DEFAULT_STEP
        self.entity_description = description

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (last_number_data := await self.async_get_last_number_data()) is not None:
            self._attr_native_value = last_number_data.native_value
            self._attr_native_min_value = (
                last_number_data.native_min_value or DEFAULT_MIN_VALUE
            )
            self._attr_native_max_value = (
                last_number_data.native_max_value or DEFAULT_MAX_VALUE
            )
            self._attr_native_step = last_number_data.native_step or DEFAULT_STEP
        self._sync_fallback()

    @callback
    def _sync_fallback(self) -> None:
        """Sync fallback data with the latest known values.

        The properties only read coordinator data, so without syncing the
        fallback attributes an entity reverts to its startup-restored values
        whenever a later refresh omits the live setting.
        """
        if (
            setting := _get_numeric_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is not None:
            candidate = setting["candidate"][0]
            self._attr_native_value = float(setting["currentValue"])
            self._attr_native_min_value = float(candidate["min"])
            self._attr_native_max_value = float(candidate["max"])
            self._attr_native_step = float(candidate.get("step", 1))

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_fallback()
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        setting = self.coordinator.get_setting(self.entity_description.key)
        return (
            super().available
            and self.coordinator.is_on
            and (
                # Controls the TV does not report are only available while a
                # restored value exists
                (setting is not None and setting["isAvailable"])
                or (setting is None and self._attr_native_value is not None)
            )
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        if (
            setting := _get_numeric_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is not None:
            return float(setting["currentValue"])
        # Fall back to the restored value until the TV reports a new one
        return self._attr_native_value

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if (
            setting := _get_numeric_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is None:
            return self._attr_native_min_value
        return float(setting["candidate"][0]["min"])

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if (
            setting := _get_numeric_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is None:
            return self._attr_native_max_value
        return float(setting["candidate"][0]["max"])

    @property
    @override
    def native_step(self) -> float | None:
        """Return the increment/decrement step."""
        if (
            setting := _get_numeric_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is None:
            return self._attr_native_step
        return float(setting["candidate"][0].get("step", 1))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the picture quality setting.

        The step reported by the TV may allow fractional values, so only
        whole numbers are converted to int to avoid trailing ".0" noise.
        """
        if value.is_integer():
            setting_value = str(int(value))
        else:
            setting_value = str(value)
        await self.coordinator.async_set_picture_quality(
            self.entity_description.key, setting_value
        )
