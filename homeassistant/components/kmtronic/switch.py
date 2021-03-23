"""KMtronic Switch integration."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REVERSE, DATA_COORDINATOR, DATA_HUB, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    reverse = entry.options.get(CONF_REVERSE, False)
    await hub.async_get_relays()

    async_add_entities(
        [
            KMtronicSwitch(coordinator, relay, reverse, entry.entry_id)
            for relay in hub.relays
        ]
    )


class KMtronicSwitch(CoordinatorEntity, SwitchEntity):
    """KMtronic Switch Entity."""

    def __init__(self, coordinator, relay, reverse, config_entry_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._relay = relay
        self._config_entry_id = config_entry_id
        self._reverse = reverse

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Relay{self._relay.id}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return f"{self._config_entry_id}_relay{self._relay.id}"

    @property
    def is_on(self):
        """Return entity state."""
        if self._reverse:
            return not self._relay.is_on
        return self._relay.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        if self._reverse:
            await self._relay.turn_off()
        else:
            await self._relay.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if self._reverse:
            await self._relay.turn_on()
        else:
            await self._relay.turn_off()
        self.async_write_ha_state()
