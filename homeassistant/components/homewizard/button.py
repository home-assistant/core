"""Support for HomeWizard buttons."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Identify button."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    features = await coordinator.api.features()
    if features.has_identify:
        async_add_entities([HomeWizardIdentifyButton(coordinator, entry)])


class HomeWizardIdentifyButton(
    CoordinatorEntity[HWEnergyDeviceUpdateCoordinator], ButtonEntity
):
    """Representation of a identify button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_identify"
        self._attr_device_info = {
            "name": entry.title,
            "manufacturer": "HomeWizard",
            "sw_version": coordinator.data["device"].firmware_version,
            "model": coordinator.data["device"].product_type,
            "identifiers": {(DOMAIN, coordinator.data["device"].serial)},
        }
        self._attr_name = "Identify"
        self._attr_icon = "mdi:magnify"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Identify the device."""
        await self.coordinator.api.identify()
