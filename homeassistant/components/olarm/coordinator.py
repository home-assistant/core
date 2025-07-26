"""The coordinator for the olarm integration to handle API and MQTT connections."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from olarmflowclient import OlarmFlowClient, OlarmFlowClientApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class OlarmDeviceData:
    """Data structure to hold Olarm device information."""

    device_name: str
    device_state: dict[str, Any] | None = None
    device_links: dict[str, Any] | None = None
    device_io: dict[str, Any] | None = None
    device_profile: dict[str, Any] | None = None
    device_profile_links: dict[str, Any] | None = None
    device_profile_io: dict[str, Any] | None = None


class OlarmDataUpdateCoordinator(DataUpdateCoordinator[OlarmDeviceData]):
    """Manages an individual olarms config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        olarm_client: OlarmFlowClient,
    ) -> None:
        """Create a new instance of the OlarmCoordinator."""

        self._oauth_session = oauth_session

        # user props
        self._user_id = entry.data["user_id"]

        # device props
        self.device_id = entry.data["device_id"]

        # olarm connect client
        self._olarm_connect_client = olarm_client

        # Initialize DataUpdateCoordinator with no update interval (one-time setup only)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=None,  # No periodic updates, MQTT handles ongoing updates
        )

    async def _async_update_data(self) -> OlarmDeviceData:
        """Fetch device information from the Olarm API."""
        try:
            device = await self._olarm_connect_client.get_device(self.device_id)
            device_data = OlarmDeviceData(
                device_name=device.get("deviceName") or "Olarm Device",
                device_state=device.get("deviceState"),
                device_links=device.get("deviceLinks"),
                device_io=device.get("deviceIO"),
                device_profile=device.get("deviceProfile"),
                device_profile_links=device.get("deviceProfileLinks"),
                device_profile_io=device.get("deviceProfileIO"),
            )

            _LOGGER.debug(
                "Device -> %s",
                {
                    "device_name": device_data.device_name,
                    "device_state": device_data.device_state,
                },
            )

        except OlarmFlowClientApiError as e:
            raise UpdateFailed("Failed to reach Olarm API") from e
        else:
            return device_data

    def async_update_from_mqtt(self, payload):
        """Update coordinator data from an MQTT payload."""
        if not self.data:
            return

        updated = False

        if "deviceState" in payload:
            self.data.device_state = payload["deviceState"]
            updated = True
        if "deviceLinks" in payload:
            self.data.device_links = payload["deviceLinks"]
            updated = True
        if "deviceIO" in payload:
            self.data.device_io = payload["deviceIO"]
            updated = True

        if updated:
            self.async_set_updated_data(self.data)
