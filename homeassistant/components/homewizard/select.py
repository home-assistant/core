"""Support for HomeWizard select platform."""

from __future__ import annotations

from homewizard_energy.models import Batteries

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomeWizardConfigEntry, HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HomeWizard select based on a config entry."""
    if entry.runtime_data.data.device.supports_batteries():
        async_add_entities(
            [
                HomeWizardBatteryModeSelectEntity(
                    coordinator=entry.runtime_data,
                )
            ]
        )


class HomeWizardBatteryModeSelectEntity(HomeWizardEntity, SelectEntity):
    """Defines a HomeWizard select entity."""

    entity_description: SelectEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)

        batteries = coordinator.data.batteries
        battery_count = batteries.battery_count if batteries is not None else None
        entity_registry_enabled_default = (
            battery_count is not None and battery_count > 0
        )
        description = SelectEntityDescription(
            key="battery_group_mode",
            translation_key="battery_group_mode",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=entity_registry_enabled_default,
            options=[
                str(mode)
                for mode in (coordinator.data.device.supported_battery_modes() or [])
            ],
        )

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return (
            self.coordinator.data.batteries.mode
            if self.coordinator.data.batteries and self.coordinator.data.batteries.mode
            else None
        )

    @homewizard_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.api.batteries(Batteries.Mode(option))
        await self.coordinator.async_request_refresh()
