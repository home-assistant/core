"""The select platform for the A. O. Smith integration."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AOSmithConfigEntry
from .coordinator import AOSmithStatusCoordinator
from .entity import AOSmithStatusEntity

HWP_LEVEL_HA_TO_AOSMITH = {
    "off": 0,
    "level1": 1,
    "level2": 2,
    "level3": 3,
}
HWP_LEVEL_AOSMITH_TO_HA = {value: key for key, value in HWP_LEVEL_HA_TO_AOSMITH.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AOSmithConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up A. O. Smith select platform."""
    data = entry.runtime_data

    async_add_entities(
        AOSmithHotWaterPlusSelectEntity(data.status_coordinator, device.junction_id)
        for device in data.status_coordinator.data.values()
        if device.supports_hot_water_plus
    )


class AOSmithHotWaterPlusSelectEntity(AOSmithStatusEntity, SelectEntity):
    """Class for the Hot Water+ select entity."""

    _attr_translation_key = "hot_water_plus_level"
    _attr_options = list(HWP_LEVEL_HA_TO_AOSMITH)

    def __init__(self, coordinator: AOSmithStatusCoordinator, junction_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, junction_id)
        self._attr_unique_id = f"hot_water_plus_level_{junction_id}"

    @property
    def suggested_object_id(self) -> str | None:
        """Override the suggested object id to make '+' get converted to 'plus' in the entity id."""
        return "hot_water_plus_level"

    @property
    def current_option(self) -> str | None:
        """Return the current Hot Water+ mode."""
        hot_water_plus_level = self.device.status.hot_water_plus_level
        return (
            None
            if hot_water_plus_level is None
            else HWP_LEVEL_AOSMITH_TO_HA.get(hot_water_plus_level)
        )

    async def async_select_option(self, option: str) -> None:
        """Set the Hot Water+ mode."""
        aosmith_hwp_level = HWP_LEVEL_HA_TO_AOSMITH[option]
        await self.client.update_mode(
            junction_id=self.junction_id,
            mode=self.device.status.current_mode,
            hot_water_plus_level=aosmith_hwp_level,
        )

        await self.coordinator.async_request_refresh()
