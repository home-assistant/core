"""Support for monitoring juicenet/juicepoint/juicebox based EVSE switches."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .entity import JuiceNetDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JuiceNet switches."""
    juicenet_data = hass.data[DOMAIN][config_entry.entry_id]
    api = juicenet_data[JUICENET_API]
    coordinator = juicenet_data[JUICENET_COORDINATOR]

    async_add_entities(
        JuiceNetChargeNowSwitch(device, coordinator) for device in api.devices
    )


class JuiceNetChargeNowSwitch(JuiceNetDevice, SwitchEntity):
    """Implementation of a JuiceNet switch."""

    _attr_translation_key = "charge_now"

    def __init__(self, device, coordinator):
        """Initialise the switch."""
        super().__init__(device, "charge_now", coordinator)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.override_time != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Charge now."""
        await self.device.set_override(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Don't charge now."""
        await self.device.set_override(False)
