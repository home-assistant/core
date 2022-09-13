"""Support for SwitchBee scenario button."""
import logging

from switchbee.api import SwitchBeeError
from switchbee.device import ApiStateCommand, DeviceType, SwitchBeeBaseDevice

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitchBeeCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, device, coordinator)
        for device in coordinator.data.values()
        if device.type == DeviceType.Scenario
    )


class Device(CoordinatorEntity, ButtonEntity):
    """Representation of an Switchbee button."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: SwitchBeeBaseDevice,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee switch."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = f"{device.zone} {device.name}"
        self._device_id = device.id
        self._attr_unique_id = f"{coordinator.mac_formated}-{device.id}"

    async def async_press(self) -> None:
        """Fire the scenario in the SwitchBee hub."""
        try:
            await self.coordinator.api.set_state(self._device_id, ApiStateCommand.ON)
        except SwitchBeeError as exp:
            _LOGGER.error("Failed to fire scenario %s, error: %s", self._attr_name, exp)
