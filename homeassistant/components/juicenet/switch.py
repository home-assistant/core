"""Support for monitoring juicenet/juicepoint/juicebox based EVSE switches."""

from typing import Any

from pyjuicenet import Charger

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JuiceNetConfigEntry, JuiceNetCoordinator
from .entity import JuiceNetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JuiceNetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JuiceNet switches."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        JuiceNetChargeNowSwitch(device, coordinator)
        for device in coordinator.juicenet_api.devices
    )


class JuiceNetChargeNowSwitch(JuiceNetEntity, SwitchEntity):
    """Implementation of a JuiceNet switch."""

    _attr_translation_key = "charge_now"

    def __init__(self, device: Charger, coordinator: JuiceNetCoordinator) -> None:
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
