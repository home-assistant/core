"""Support for HomeWizard buttons."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeWizardConfigEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Identify button."""
    if entry.runtime_data.supports_identify():
        async_add_entities([HomeWizardIdentifyButton(entry.runtime_data)])


class HomeWizardIdentifyButton(HomeWizardEntity, ButtonEntity):
    """Representation of a identify button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.IDENTIFY

    def __init__(self, coordinator: HWEnergyDeviceUpdateCoordinator) -> None:
        """Initialize button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_identify"

    @homewizard_exception_handler
    async def async_press(self) -> None:
        """Identify the device."""
        await self.coordinator.api.identify()
