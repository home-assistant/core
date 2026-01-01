"""Switch platform for Fressnapf Tracker."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FressnapfTrackerConfigEntry
from .entity import FressnapfTrackerEntity

PARALLEL_UPDATES = 1

SWITCH_ENTITY_DESCRIPTION = SwitchEntityDescription(
    translation_key="energy_saving",
    entity_category=EntityCategory.CONFIG,
    device_class=SwitchDeviceClass.SWITCH,
    key="energy_saving",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FressnapfTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fressnapf Tracker switches."""

    async_add_entities(
        FressnapfTrackerSwitch(coordinator, SWITCH_ENTITY_DESCRIPTION)
        for coordinator in entry.runtime_data
        if coordinator.data.tracker_settings.features.energy_saving_mode
    )


class FressnapfTrackerSwitch(FressnapfTrackerEntity, SwitchEntity):
    """Fressnapf Tracker switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self.coordinator.client.set_energy_saving(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.coordinator.client.set_energy_saving(False)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        if TYPE_CHECKING:
            # The entity is not created if energy_saving is None
            assert self.coordinator.data.energy_saving is not None
        return self.coordinator.data.energy_saving.value == 1
