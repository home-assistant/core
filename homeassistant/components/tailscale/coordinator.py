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

    # Track devices from previous update to detect removals
    previous_devices: set[str] = set()

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Tailscale coordinator."""
        session = async_get_clientsession(hass)
        self.tailscale = Tailscale(
            session=session,
            api_key=config_entry.data[CONF_API_KEY],
            tailnet=config_entry.data[CONF_TAILNET],
        )

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
            data = await self.tailscale.devices()
        except TailscaleAuthenticationError as err:
            raise ConfigEntryAuthFailed from err

        # Identify devices that exist in HA but no longer exist in Tailscale
        current_devices = set(data)
        if stale_devices := self.previous_devices - current_devices:
            device_registry = dr.async_get(self.hass)

            # Remove each stale device from the device registry
            for device_id in stale_devices:
                if device := device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                    LOGGER.debug(
                        "Removed device %s as it no longer exists in Tailscale",
                        device_id,
                    )

        # Update our tracking set for the next poll
        self.previous_devices = current_devices

        return data
