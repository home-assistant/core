"""Support for SwitchBee scenario button."""

from switchbee.api import SwitchBeeError
from switchbee.device import ApiStateCommand, DeviceType, SwitchBeeBaseDevice

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee button."""
    coordinator: SwitchBeeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SwitchBeeButton(switchbee_device, coordinator)
        for switchbee_device in coordinator.data.values()
        if switchbee_device.type == DeviceType.Scenario
    )


class SwitchBeeButton(CoordinatorEntity[SwitchBeeCoordinator], ButtonEntity):
    """Representation of an Switchbee button."""

    def __init__(
        self,
        device: SwitchBeeBaseDevice,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee switch."""
        super().__init__(coordinator)
        self._attr_name = f"{device.zone} {device.name}"
        self._device_id: int = device.id
        self._attr_unique_id = f"{coordinator.mac_formated}-{device.id}"

    async def async_press(self) -> None:
        """Fire the scenario in the SwitchBee hub."""
        try:
            await self.coordinator.api.set_state(self._device_id, ApiStateCommand.ON)
        except SwitchBeeError as exp:
            raise HomeAssistantError(
                f"Failed to fire scenario {self._attr_name}, {str(exp)}"
            ) from exp
