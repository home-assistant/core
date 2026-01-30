"""DataUpdateCoordinator for the Tailscale integration."""

from __future__ import annotations

from tailscale import Device, Tailscale, TailscaleAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_TAILNET, DOMAIN, LOGGER, SCAN_INTERVAL


class TailscaleDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """The Tailscale Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Tailscale coordinator."""
        session = async_get_clientsession(hass)
        self.tailscale = Tailscale(
            session=session,
            api_key=config_entry.data[CONF_API_KEY],
            tailnet=config_entry.data[CONF_TAILNET],
        )
        self.previous_devices: set[str] = set()

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch devices from Tailscale and remove stale devices from HA."""
        try:
            devices = await self.tailscale.devices()
        except TailscaleAuthenticationError as err:
            raise ConfigEntryAuthFailed from err

        # Get current device IDs
        current_device_ids = set(devices.keys())

        # Find devices that were removed from Tailscale
        if self.previous_devices:
            stale_device_ids = self.previous_devices - current_device_ids
            if stale_device_ids:
                await self._remove_stale_devices(stale_device_ids)

        # Update previous devices set for next comparison
        self.previous_devices = current_device_ids

        return devices

    async def _remove_stale_devices(self, stale_device_ids: set[str]) -> None:
        """Remove devices that no longer exist in Tailscale."""
        device_registry = dr.async_get(self.hass)

        for device_id in stale_device_ids:
            device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
            if device:
                LOGGER.debug("Removing stale device: %s", device_id)
                device_registry.async_remove_device(device.id)
