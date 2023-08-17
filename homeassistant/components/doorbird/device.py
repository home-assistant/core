"""Support for DoorBird devices."""
from __future__ import annotations

import logging
from typing import Any

from doorbirdpy import DoorBird

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util, slugify

from .const import API_URL

_LOGGER = logging.getLogger(__name__)


class ConfiguredDoorBird:
    """Attach additional information to pass along with configured device."""

    def __init__(
        self,
        device: DoorBird,
        name: str | None,
        custom_url: str | None,
        token: str,
        event_entity_ids: dict[str, str],
    ) -> None:
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._token = token
        self._event_entity_ids = event_entity_ids
        self.events: list[str] = []
        self.door_station_events: list[str] = []

    def update_events(self, events: list[str]) -> None:
        """Update the doorbird events."""
        self.events = events
        self.door_station_events = [
            self._get_event_name(event) for event in self.events
        ]

    @property
    def name(self) -> str | None:
        """Get custom device name."""
        return self._name

    @property
    def device(self) -> DoorBird:
        """Get the configured device."""
        return self._device

    @property
    def custom_url(self) -> str | None:
        """Get custom url for device."""
        return self._custom_url

    @property
    def token(self) -> str:
        """Get token for device."""
        return self._token

    def register_events(self, hass: HomeAssistant) -> None:
        """Register events on device."""
        # Get the URL of this server
        hass_url = get_url(hass, prefer_external=False)

        # Override url if another is specified in the configuration
        if self.custom_url is not None:
            hass_url = self.custom_url

        if not self.door_station_events:
            # User may not have permission to get the favorites
            return

        favorites = self.device.favorites()
        for event in self.door_station_events:
            if self._register_event(hass_url, event, favs=favorites):
                _LOGGER.info(
                    "Successfully registered URL for %s on %s", event, self.name
                )

    @property
    def slug(self) -> str:
        """Get device slug."""
        return slugify(self._name)

    def _get_event_name(self, event: str) -> str:
        return f"{self.slug}_{event}"

    def _register_event(
        self, hass_url: str, event: str, favs: dict[str, Any] | None = None
    ) -> bool:
        """Add a schedule entry in the device for a sensor."""
        url = f"{hass_url}{API_URL}/{event}?token={self._token}"

        # Register HA URL as webhook if not already, then get the ID
        if self.webhook_is_registered(url, favs=favs):
            return True

        self.device.change_favorite("http", f"Home Assistant ({event})", url)
        if not self.webhook_is_registered(url):
            _LOGGER.warning(
                'Unable to set favorite URL "%s". Event "%s" will not fire',
                url,
                event,
            )
            return False
        return True

    def webhook_is_registered(
        self, url: str, favs: dict[str, Any] | None = None
    ) -> bool:
        """Return whether the given URL is registered as a device favorite."""
        return self.get_webhook_id(url, favs) is not None

    def get_webhook_id(
        self, url: str, favs: dict[str, Any] | None = None
    ) -> str | None:
        """Return the device favorite ID for the given URL.

        The favorite must exist or there will be problems.
        """
        favs = favs if favs else self.device.favorites()

        if "http" not in favs:
            return None

        for fav_id in favs["http"]:
            if favs["http"][fav_id]["value"] == url:
                return fav_id

        return None

    def get_event_data(self, event: str) -> dict[str, str | None]:
        """Get data to pass along with HA event."""
        return {
            "timestamp": dt_util.utcnow().isoformat(),
            "live_video_url": self._device.live_video_url,
            "live_image_url": self._device.live_image_url,
            "rtsp_live_video_url": self._device.rtsp_live_video_url,
            "html5_viewer_url": self._device.html5_viewer_url,
            ATTR_ENTITY_ID: self._event_entity_ids.get(event),
        }
