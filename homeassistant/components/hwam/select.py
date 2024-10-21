"""The controls for smart controlled stoves."""

from pystove import DATA_BURN_LEVEL

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator


class SelectBurnLevel(CoordinatorEntity[StoveDataUpdateCoordinator], SelectEntity):
    """The button to start the combustion.

    If the stove is already burning, command is omitted.
    """

    _attr_has_entity_name = True
    _attr_options = ["0", "1", "2", "3", "4", "5"]

    _coordinator: StoveDataUpdateCoordinator

    def __init__(self, coordinator: StoveDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.key = DATA_BURN_LEVEL
        self.translation_key = DATA_BURN_LEVEL
        self._attr_unique_id = f"{coordinator.device_id}_{DATA_BURN_LEVEL}"
        self._attr_device_info = coordinator.device_info()

    async def async_select_option(self, option: str) -> None:
        """Change the burn level."""
        await self.coordinator.api.set_burn_level(option)
        await self.coordinator.async_request_refresh()

    @property
    def current_option(self) -> str:
        """Return the current burn level."""
        return self.coordinator.data[DATA_BURN_LEVEL]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the buttons."""
    coordinator: StoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SelectBurnLevel(coordinator)])
