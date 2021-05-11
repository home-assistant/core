"""Support for the Dynalite channels and presets as switches."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .dynalitebase import DynaliteBase, async_setup_entry_base


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Record the async_add_entities function to add them later when received from Dynalite."""
    async_setup_entry_base(
        hass, config_entry, async_add_entities, "switch", DynaliteSwitch
    )


class DynaliteSwitch(DynaliteBase, SwitchEntity):
    """Representation of a Dynalite Channel as a Home Assistant Switch."""

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._device.async_turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._device.async_turn_off()
