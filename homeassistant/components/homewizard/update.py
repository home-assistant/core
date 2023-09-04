"""HomeWizard platform that offers update entities."""
from __future__ import annotations

from homewizard_energy.const import LATEST_STABLE_FIRMWARE

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update platform."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            HomeWizardUpdateEntity(
                coordinator,
                entry,
            ),
        ]
    )


class HomeWizardUpdateEntity(HomeWizardEntity, UpdateEntity):
    """Representation of a HomeWizard update entity."""

    _attr_auto_update = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_update"

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self.coordinator.data.device.firmware_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.data.device.product_type is None:
            return None

        try:
            return LATEST_STABLE_FIRMWARE[self.coordinator.data.device.product_type]
        except KeyError:
            return None

    def release_notes(self) -> str | None:
        """Return the update instructions."""
        return (
            "**To install latest firmware**\n"
            "\n"
            "  1. Make sure you have enabled 'Cloud connection'\n"
            "  2. Open the HomeWizard Energy app\n"
            "  3. Go to Settings → Meters and find your device\n"
            "  4. Press '...' in the top right\n"
            "  5. Select 'Check for updates'"
        )
