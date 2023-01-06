"""Support for HomeWizard buttons."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Identify button."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    features = await coordinator.api.features()
    if features.has_identify:
        async_add_entities([HomeWizardIdentifyButton(coordinator, entry)])


class HomeWizardIdentifyButton(HomeWizardEntity, ButtonEntity):
    """Representation of a identify button."""

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_identify"
        self._attr_name = "Identify"
        self._attr_icon = "mdi:magnify"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @homewizard_exception_handler
    async def async_press(self) -> None:
        """Identify the device."""
        await self.coordinator.api.identify()
