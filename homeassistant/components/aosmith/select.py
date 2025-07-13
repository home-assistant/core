"""The select platform for the A. O. Smith integration."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AOSmithConfigEntry
from .coordinator import AOSmithStatusCoordinator
from .entity import AOSmithStatusEntity

HWP_LEVEL_HA_TO_AOSMITH = {
    "Off": 0,
    "1": 1,
    "2": 2,
    "3": 3,
}
HWP_LEVEL_AOSMITH_TO_HA = {value: key for key, value in HWP_LEVEL_HA_TO_AOSMITH.items()}

x = list(HWP_LEVEL_AOSMITH_TO_HA)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AOSmithConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up A. O. Smith select platform."""
    data = entry.runtime_data

    async_add_entities(
        [
            AOSmithHotWaterPlusSelectEntity(data.status_coordinator, device.junction_id)
            for device in data.status_coordinator.data.values()
            if device.supports_hot_water_plus
        ]
    )


class AOSmithHotWaterPlusSelectEntity(AOSmithStatusEntity, SelectEntity):
    """Class for the Hot Water+ select entity."""

    _attr_options = list(HWP_LEVEL_HA_TO_AOSMITH)
    _attr_translation_key = "hot_water_plus"

    def __init__(self, coordinator: AOSmithStatusCoordinator, junction_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, junction_id)
        self._attr_unique_id = junction_id

    @property
    def current_option(self) -> str | None:
        """Return the current Hot Water+ mode."""
        return HWP_LEVEL_HA_TO_AOSMITH.get(self.device.status.hot_water_plus_level)

    async def async_select_option(self, option: str) -> None:
        """Set the Hot Water+ mode."""
        if option not in self.options:
            raise HomeAssistantError(f"Invalid option: {option}")

        aosmith_hwp_level = HWP_LEVEL_HA_TO_AOSMITH.get(option)
        if aosmith_hwp_level is not None:
            await self.client.update_mode(
                junction_id=self.junction_id,
                mode=self.device.status.current_mode,
                hot_water_plus_level=aosmith_hwp_level,
            )

            await self.coordinator.async_request_refresh()

    @property
    def options(self) -> list[str]:
        """Return the list of available operation modes."""
        return [mode.original_name for mode in self.device.supported_modes]
