"""Support for homekit switch."""
import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, HOMEKIT, STATUS_RUNNING
from .entity import HomeKitEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the homekit sensors."""

    homekit = hass.data[DOMAIN][config_entry.entry_id][HOMEKIT]
    mac = homekit.driver.state.mac
    bridge_name = homekit.bridge.display_name

    async_add_entities(
        [HomeKitBridgeSwitch(config_entry, mac, bridge_name, homekit)], False
    )


class HomeKitBridgeSwitch(HomeKitEntity, SwitchEntity):
    """Representation of an homekit remote control sensor."""

    def __init__(self, config_entry, mac, bridge_name, homekit):
        """Init the remote control sensor."""
        super().__init__(config_entry, mac, bridge_name)
        self._homekit = homekit

    @property
    def name(self):
        """Switch Name."""
        return self._bridge_name

    @property
    def unique_id(self):
        """Switch Uniqueid."""
        return f"{self._config_entry.entry_id}_bridge_switch"

    @property
    def is_on(self) -> bool:
        """Get whether bridge is running."""
        return self._homekit.status == STATUS_RUNNING

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the bridge."""
        await self._homekit.async_stop()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the bridge."""
        await self._homekit.async_stop()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self._homekit.async_add_bridge_status_listener(self.async_write_ha_state)
        )
