"""KMtronic Switch integration."""
from datetime import timedelta
import logging

import aiohttp
import async_timeout

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DATA_HOST, DATA_HUB, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    host = hass.data[DOMAIN][entry.entry_id][DATA_HOST]
    await hub.async_get_relays()

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                await hub.async_update_relays()
        except aiohttp.client_exceptions.ClientConnectorError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{MANUFACTURER} {hub.name}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    async_add_entities(
        [KMtronicSwitch(coordinator, host, relay) for relay in hub.relays]
    )


class KMtronicSwitch(CoordinatorEntity, SwitchEntity):
    """KMtronic Switch Entity."""

    def __init__(self, coordinator, host, relay):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._host = host
        self._relay = relay

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.last_update_success

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Relay{self._relay.id}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return f"{self._host}_relay{self._relay.id}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def is_on(self):
        """Return entity state."""
        return self._relay.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._relay.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._relay.turn_off()
        self.async_write_ha_state()
