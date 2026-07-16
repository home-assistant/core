"""Radar configuration selects for LinknLink eMotion Ultra."""

from typing import override

from aiolinknlink import UltraError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 1

LEVEL_OPTIONS = ["level_0", "level_1", "level_2"]
INSTALL_MODE_OPTIONS = ["ceiling", "wall"]
INSTALL_DIRECTION_OPTIONS = ["down", "up"]

RADAR_SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="radar_sensitivity",
        translation_key="radar_sensitivity",
        entity_category=EntityCategory.CONFIG,
        options=LEVEL_OPTIONS,
    ),
    SelectEntityDescription(
        key="radar_trigger_speed",
        translation_key="radar_trigger_speed",
        entity_category=EntityCategory.CONFIG,
        options=LEVEL_OPTIONS,
    ),
    SelectEntityDescription(
        key="radar_install_mode",
        translation_key="radar_install_mode",
        entity_category=EntityCategory.CONFIG,
        options=INSTALL_MODE_OPTIONS,
    ),
    SelectEntityDescription(
        key="radar_install_direction",
        translation_key="radar_install_direction",
        entity_category=EntityCategory.CONFIG,
        options=INSTALL_DIRECTION_OPTIONS,
    ),
)

RADAR_SENSITIVITY_DESCRIPTION = RADAR_SELECT_DESCRIPTIONS[0]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device-verified radar configuration selects."""
    async_add_entities(
        LinknLinkRadarSelect(entry.runtime_data, description)
        for description in RADAR_SELECT_DESCRIPTIONS
    )


class LinknLinkRadarSelect(LinknLinkEntity, SelectEntity):
    """Configure one Ultra radar enum with a device read-back."""

    entity_description: SelectEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether radar configuration is readable."""
        position_state = self.coordinator.position_state
        return (
            position_state is not None
            and position_state.subscribed
            and self._current_value() is not None
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the device-read radar configuration option."""
        value = self._current_value()
        options = self.entity_description.options
        if options is None or value is None or not 0 <= value < len(options):
            return None
        return options[value]

    def _current_value(self) -> int | None:
        """Return the raw device-read option value."""
        status = self.coordinator.radar_status
        if status is None:
            return None
        match self.entity_description.key:
            case "radar_sensitivity":
                return status.sensitivity
            case "radar_trigger_speed":
                return status.trigger_speed
            case "radar_install_mode":
                return status.install_mode
            case "radar_install_direction":
                return status.install_direction
            case _:
                return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Set a radar option and require a matching device read-back."""
        options = self.entity_description.options
        assert options is not None
        try:
            value = options.index(option)
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_radar_option",
            ) from err
        try:
            await self._async_set_option(value)
        except (OSError, UltraError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_error",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    async def _async_set_option(self, value: int) -> None:
        """Dispatch a validated option to the matching coordinator operation."""
        match self.entity_description.key:
            case "radar_sensitivity":
                await self.coordinator.async_set_radar_sensitivity(value)
            case "radar_trigger_speed":
                await self.coordinator.async_set_radar_trigger_speed(value)
            case "radar_install_mode":
                await self.coordinator.async_set_radar_install_mode(value)
            case "radar_install_direction":
                await self.coordinator.async_set_radar_install_direction(value)
            case _:
                raise ValueError(self.entity_description.key)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to radar configuration changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_config_listener(self._async_handle_config_update)
        )

    @callback
    def _async_handle_config_update(self) -> None:
        """Write a device-read radar configuration update."""
        self.async_write_ha_state()
