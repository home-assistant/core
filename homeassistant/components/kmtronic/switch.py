"""KMtronic Switch integration."""
import urllib.parse

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REVERSE, DATA_COORDINATOR, DATA_HUB, DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    reverse = entry.options.get(CONF_REVERSE, False)
    await hub.async_get_relays()

    async_add_entities(
        [
            KMtronicSwitch(hass, coordinator, relay, reverse, entry.entry_id)
            for relay in hub.relays
        ]
    )


class KMtronicSwitch(CoordinatorEntity, SwitchEntity):
    """KMtronic Switch Entity."""

    def __init__(self, hass, coordinator, relay, reverse, config_entry_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._relay = relay
        self._config_entry_id = config_entry_id
        self._reverse = reverse

        hub_host = hass.data[DOMAIN][self._config_entry_id][DATA_HUB].host
        hostname = urllib.parse.urlsplit(hub_host).hostname
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._config_entry_id)},
            "name": f"Controller {hostname}",
            "manufacturer": MANUFACTURER,
            "configuration_url": hub_host,
        }

        self._attr_name = f"Relay{self._relay.id}"
        self._attr_unique_id = f"{self._config_entry_id}_relay{self._relay.id}"

    @property
    def is_on(self):
        """Return entity state."""
        if self._reverse:
            return not self._relay.is_energised
        return self._relay.is_energised

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        if self._reverse:
            await self._relay.de_energise()
        else:
            await self._relay.energise()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if self._reverse:
            await self._relay.energise()
        else:
            await self._relay.de_energise()
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs) -> None:
        """Toggle the switch."""
        await self._relay.toggle()
        self.async_write_ha_state()
