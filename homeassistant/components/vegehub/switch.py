"""Switch configuration for VegeHub integration."""

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VegeHubConfigEntry, VegeHubCoordinator
from .entity import VegeHubEntity

SWITCH_TYPES: dict[str, SwitchEntityDescription] = {
    "switch": SwitchEntityDescription(
        key="switch",
        translation_key="switch",
        device_class=SwitchDeviceClass.SWITCH,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VegeHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VegeHub switches from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        VegeHubSwitch(
            index=i,
            duration=600,  # Default duration of 10 minutes
            coordinator=coordinator,
            description=SWITCH_TYPES["switch"],
        )
        for i in range(coordinator.vegehub.num_actuators)
    )


class VegeHubSwitch(VegeHubEntity, SwitchEntity):
    """Class for VegeHub Switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        index: int,
        duration: int,
        coordinator: VegeHubCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        # Set unique ID for pulling data from the coordinator
        self.data_key = f"actuator_{index}"
        self._attr_unique_id = f"{self._mac_address}_{self.data_key}"
        self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_available = False
        self.index = index
        self.duration = duration

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        if self.coordinator.data is None or self._attr_unique_id is None:
            return False
        return self.coordinator.data.get(self.data_key, 0) > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.vegehub.set_actuator(1, self.index, self.duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.vegehub.set_actuator(0, self.index, self.duration)
