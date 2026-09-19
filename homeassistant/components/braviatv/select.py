"""Select support for Bravia TV."""

from typing import Any, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    BraviaTVConfigEntry,
    BraviaTVCoordinator,
    BraviaTVPictureCoordinator,
)
from .entity import get_device_info


def _get_enum_picture_setting(
    coordinator: BraviaTVPictureCoordinator, target: str
) -> dict[str, Any] | None:
    """Return the enum picture setting for a target, if supported."""
    if (setting := coordinator.get_setting(target)) is None:
        return None
    # Enum settings have a candidate per allowed value, numeric
    # settings have a single candidate with a range.
    candidates = setting["candidate"]
    if isinstance(candidates[0], dict) and "min" in candidates[0]:
        return None
    return setting


def _get_picture_setting_options(setting: dict[str, Any]) -> list[str]:
    """Return the options for an enum picture setting.

    The candidates are either plain values or dicts with a "value" key.
    """
    return [
        candidate["value"] if isinstance(candidate, dict) else candidate
        for candidate in setting["candidate"]
    ]


SELECTS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="pictureMode",
        translation_key="picture_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:television-shimmer",
    ),
    SelectEntityDescription(
        key="colorSpace",
        translation_key="color_space",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:palette-outline",
    ),
    SelectEntityDescription(
        key="hdrMode",
        translation_key="hdr_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:hdr",
    ),
    SelectEntityDescription(
        key="lightSensor",
        translation_key="light_sensor",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:brightness-auto",
    ),
    SelectEntityDescription(
        key="colorTemperature",
        translation_key="color_temperature",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bravia TV Select entities.

    Entities are added even if the TV is off, so the last state can be
    restored while waiting for the TV to come back.
    """

    coordinator = config_entry.runtime_data.coordinator
    picture_coordinator = config_entry.runtime_data.picture_coordinator
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        BraviaTVSelect(coordinator, picture_coordinator, unique_id, description)
        for description in SELECTS
    )


class BraviaTVSelect(
    CoordinatorEntity[BraviaTVPictureCoordinator], SelectEntity, RestoreEntity
):
    """Representation of a Bravia TV Select."""

    _attr_has_entity_name = True
    entity_description: SelectEntityDescription

    def __init__(
        self,
        main_coordinator: BraviaTVCoordinator,
        picture_coordinator: BraviaTVPictureCoordinator,
        unique_id: str,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(picture_coordinator)
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = get_device_info(main_coordinator, unique_id)
        self._attr_options: list[str] = []
        self.entity_description = description

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            self._attr_current_option = last_state.state
            self._attr_options = [last_state.state]

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.is_on

    @property
    @override
    def options(self) -> list[str]:
        """Return the available options."""
        if (
            setting := _get_enum_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is None:
            return self._attr_options
        return _get_picture_setting_options(setting)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if (
            setting := _get_enum_picture_setting(
                self.coordinator, self.entity_description.key
            )
        ) is not None:
            return str(setting["currentValue"])
        # Fall back to the restored option until the TV reports a new one
        return self._attr_current_option

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.async_set_picture_quality(
            self.entity_description.key, option
        )
