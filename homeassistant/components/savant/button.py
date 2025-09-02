"""Buttons for Savant Home Automation."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SavantConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config: SavantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator = config.runtime_data
    buttons = [RestartButton(coordinator)]

    async_add_entities(buttons)
    coordinator.buttons.extend(buttons)


class RestartButton(CoordinatorEntity, ButtonEntity):
    """Button to restart a Savant matrix."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Restart"
    _attr_has_entity_name = True

    @property
    def unique_id(self):
        """The unique id of the sensor - uses the savantID of the coordinator."""
        return f"{self.coordinator.info['savantID']}_restart"

    @property
    def device_info(self):
        """Links to the device for the switch itself, rather than one of the ports."""
        return dr.DeviceInfo(identifiers={(DOMAIN, self.coordinator.info["savantID"])})

    async def async_press(self) -> None:
        """Send a reboot command."""
        await self.coordinator.api.reboot()
