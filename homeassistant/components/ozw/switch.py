"""Representation of Z-Wave switches."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave switch from config entry."""

    @callback
    def async_add_switch(value):
        """Add Z-Wave Switch."""
        switch = ZWaveSwitch(value)

        async_add_entities([switch])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_{SWITCH_DOMAIN}", async_add_switch
        )
    )


class ZWaveSwitch(ZWaveDeviceEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    @property
    def is_on(self):
        """Return a boolean for the state of the switch."""
        return bool(self.values.primary.value)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.values.primary.send_value(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.values.primary.send_value(False)
