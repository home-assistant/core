"""DataUpdateCoordinator for Vitrea integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from vitreaclient import DeviceStatus, VitreaClient, VitreaResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map device status to platform names
DEVICE_STATUS_TO_PLATFORM = {
    DeviceStatus.BLIND: "cover",
    # Add more mappings as needed
}


class VitreaCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator to manage Vitrea device data and dynamic entity discovery."""

    def __init__(
        self, hass: HomeAssistant, client: VitreaClient, config_entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        # Use a longer update interval since we're primarily event-driven
        # This serves as a fallback to ensure we don't lose connection
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),  # Fallback polling
            config_entry=config_entry,
        )
        self.client = client
        self._discovered_entities: set[str] = set()
        # Store callbacks by platform type
        self._entity_add_callbacks: dict[
            str, Callable[[str, dict[str, Any]], None]
        ] = {}

        # Set up event listeners for real-time updates
        self._unsubscribe_status = self.client.on(
            VitreaResponse.STATUS, self._handle_status_event
        )

    def set_entity_add_callback(
        self, platform: str, entity_callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Set callback to add new entities dynamically for a specific platform."""
        self._entity_add_callbacks[platform] = entity_callback

    @callback
    def _handle_status_event(self, event: Any) -> None:
        """Handle real-time status updates from Vitrea."""
        # Determine platform type from device status
        platform = DEVICE_STATUS_TO_PLATFORM.get(event.status)
        if not platform:
            _LOGGER.debug("Unhandled device status: %s", event.status)
            return

        entity_id = f"{event.node}_{event.key}"

        # Update existing entity data
        if not self.data:
            self.data = {}

        # Store platform-specific data
        entity_data = {
            "node": event.node,
            "key": event.key,
            "status": event.status,
            "platform": platform,
        }

        # Add platform-specific data based on device type
        if event.status == DeviceStatus.BLIND:
            entity_data["position"] = int(event.data)

        self.data[entity_id] = entity_data

        # Handle new entity discovery
        if entity_id not in self._discovered_entities:
            self._discovered_entities.add(entity_id)
            _LOGGER.debug("New %s entity discovered: %s", platform, entity_id)

            # Notify appropriate platform to add new entity
            platform_callback = self._entity_add_callbacks.get(platform)
            if platform_callback:
                platform_callback(entity_id, self.data[entity_id])
            else:
                _LOGGER.warning("No callback registered for platform %s", platform)

        # Notify all listeners of the data update
        self.async_set_updated_data(self.data)

    def get_entities_by_platform(self, platform: str) -> dict[str, dict[str, Any]]:
        """Get all entities for a specific platform."""
        if not self.data:
            return {}

        return {
            entity_id: data
            for entity_id, data in self.data.items()
            if data.get("platform") == platform
        }

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Vitrea (fallback polling)."""
        try:
            # Request status update - this triggers status events
            await self.client.status_request()

        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with Vitrea: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Vitrea API error: {err}") from err

        # Return current data - updated via events
        return self.data or {}

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.client.connect()
        except (ConnectionError, TimeoutError, OSError) as err:
            _LOGGER.error("Failed to setup Vitrea coordinator: %s", err)
            raise

    async def async_shutdown(self) -> None:
        """Clean up the coordinator."""
        try:
            if self._unsubscribe_status:
                self._unsubscribe_status()
            if hasattr(self.client, "disconnect"):
                await self.client.disconnect()
        except (ConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Error disconnecting Vitrea client: %s", err)
