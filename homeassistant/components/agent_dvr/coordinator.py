"""DataUpdateCoordinator for Agent DVR."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AgentDVRAuthError, AgentDVRClient, AgentDVRConnectionError
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def device_key(oid: int, ot_id: int) -> str:
    """Build the dict key used to look up a device in coordinator.data."""
    return f"{oid}_{ot_id}"


class AgentDVRDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls getStatus + getObjects on a fixed interval."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, client: AgentDVRClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="agent_dvr",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.client.get_status()
            objects = await self.client.get_objects()
        except AgentDVRAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except AgentDVRConnectionError as err:
            raise UpdateFailed(f"Agent DVR unreachable: {err}") from err

        devices: dict[str, dict[str, Any]] = {}
        for obj in objects.get("objectList", []):
            devices[device_key(int(obj["id"]), int(obj["typeID"]))] = obj

        return {
            "status": status,
            "locations": objects.get("locations", []),
            "alert_groups": objects.get("alertGroups", []),
            "devices": devices,
        }


EVENT_COUNT_WINDOW_SECONDS = 24 * 3600
EVENT_COUNT_SCAN_INTERVAL = timedelta(minutes=5)


class AgentDVREventCountCoordinator(DataUpdateCoordinator[dict[str, int]]):
    """Polls eventcounts.json per camera on a slower interval.

    Kept separate from the main coordinator so this per-device event-count
    endpoint doesn't multiply the request rate of the core polling loop.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: AgentDVRClient,
        camera_keys: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="agent_dvr_event_counts",
            update_interval=EVENT_COUNT_SCAN_INTERVAL,
        )
        self.client = client
        self._camera_keys = camera_keys

    async def _async_update_data(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for key in self._camera_keys:
            oid_str, ot_str = key.split("_")
            try:
                counts[key] = await self.client.get_event_count(
                    int(oid_str), int(ot_str), EVENT_COUNT_WINDOW_SECONDS
                )
            except AgentDVRConnectionError as err:
                raise UpdateFailed(f"Agent DVR unreachable: {err}") from err
        return counts
