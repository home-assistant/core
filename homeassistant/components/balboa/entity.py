"""Balboa entities."""

from __future__ import annotations

from pybalboa import EVENT_UPDATE, SpaClient

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class BalboaEntity(Entity):
    """Balboa base entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, client: SpaClient, key: str) -> None:
        """Initialize the control."""
        mac = client.mac_address
        model = client.model
        self._attr_unique_id = f'{model}-{key}-{mac.replace(":","")[-6:]}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=model,
            manufacturer="Balboa Water Group",
            model=model,
            sw_version=client.software_version,
            connections={(CONNECTION_NETWORK_MAC, mac)},
        )
        self._client = client

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        return not self._client.available

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(self._client.on(EVENT_UPDATE, self.async_write_ha_state))
