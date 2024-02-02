"""Support for SwitchBot binary sensors."""
from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.binary_sensors
    )


class SwitchBotCloudBinarySensor(SwitchBotCloudEntity, BinarySensorEntity):
    """Representation of a SwitchBot binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return
        self._attr_is_on = self.coordinator.data["openState"] != "close"
        self.async_write_ha_state()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudBinarySensor:
    """Make a SwitchBotCloudBinarySensor."""
    if isinstance(device, Device):
        return SwitchBotCloudBinarySensor(api, device, coordinator)
    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
