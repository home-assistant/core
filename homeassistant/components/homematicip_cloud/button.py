"""Support for HomematicIP Cloud button devices."""

from __future__ import annotations

from homematicip.device import WallMountedGarageDoorController

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP button from a config entry."""
    hap = config_entry.runtime_data

    async_add_entities(
        HomematicipGarageDoorControllerButton(hap, device)
        for device in hap.home.devices
        if isinstance(device, WallMountedGarageDoorController)
    )


class HomematicipGarageDoorControllerButton(HomematicipGenericEntity, ButtonEntity):
    """Representation of the HomematicIP Wall mounted Garage Door Controller."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize a wall mounted garage door controller."""
        super().__init__(hap, device)
        self._attr_icon = "mdi:arrow-up-down"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._device.send_start_impulse_async()
