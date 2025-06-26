"""The controls for smart controlled stoves."""

from pystove import DATA_PHASE

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import StoveDataUpdateCoordinator

KEY_BUTTON_START = "button_start"


class StartButton(ButtonEntity):
    """The button to start the combustion.

    If the stove is already burning, command is omitted.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:power"

    _coordinator: StoveDataUpdateCoordinator

    def __init__(self, coordinator: StoveDataUpdateCoordinator) -> None:
        """Initialize the button."""
        self._coordinator = coordinator
        self.key = KEY_BUTTON_START
        self.translation_key = KEY_BUTTON_START
        self._attr_unique_id = f"{coordinator.device_id}_{KEY_BUTTON_START}"
        self._attr_device_info = coordinator.device_info()

    async def async_press(self) -> None:
        """Handle the button press."""
        if self._coordinator.data[DATA_PHASE] == "Standby":
            LOGGER.info("Sending command to start combustion")
            await self._coordinator.api.start()
            await self._coordinator.async_request_refresh()
        else:
            LOGGER.debug("Omitted to send command to start combustion")
            LOGGER.debug(f"phase = {self._coordinator.data[DATA_PHASE]}")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the buttons."""
    coordinator: StoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StartButton(coordinator)])
