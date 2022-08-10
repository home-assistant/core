"""Switch platform for MicroBot."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_NAME, DOMAIN, ICON
from .entity import MicroBotEntity


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up MicroBot based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([MicroBotBinarySwitch(coordinator, entry)])


class MicroBotBinarySwitch(MicroBotEntity, SwitchEntity, RestoreEntity):
    """MicroBot switch class."""

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        await self.coordinator.api.connect()
        await self.coordinator.api.push_on()
        await self.coordinator.api.disconnect()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        await self.coordinator.api.connect()
        await self.coordinator.api.push_off()
        await self.coordinator.api.disconnect()
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{DEFAULT_NAME}"

    @property
    def icon(self):
        """Return the icon of this switch."""
        return ICON

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.coordinator.api.is_on

    @property
    def available(self) -> bool:
        """Return true if the switch is available."""
        return True

    @property
    def assumed_state(self) -> bool:
        """Return true if the state is assumed."""
        return False
