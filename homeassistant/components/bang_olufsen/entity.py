"""Entity representing a Bang & Olufsen device."""
from __future__ import annotations

from typing import cast

from mozart_api.models import (
    PlaybackContentMetadata,
    PlaybackProgress,
    RenderingState,
    Source,
    VolumeLevel,
    VolumeMute,
    VolumeState,
)
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class BangOlufsenBase:
    """Base class for BangOlufsen Home Assistant objects."""

    def __init__(self, entry: ConfigEntry, client: MozartClient) -> None:
        """Initialize the object."""

        # Set the MozartClient
        self._client = client

        # get the input from the config entry.
        self.entry: ConfigEntry = entry

        # Set the configuration variables.
        self._host: str = self.entry.data[CONF_HOST]
        self._name: str = self.entry.title
        self._unique_id: str = cast(str, self.entry.unique_id)

        # Objects that get directly updated by notifications.
        self._playback_metadata: PlaybackContentMetadata = PlaybackContentMetadata()
        self._playback_progress: PlaybackProgress = PlaybackProgress(total_duration=0)
        self._playback_source: Source = Source()
        self._playback_state: RenderingState = RenderingState()
        self._source_change: Source = Source()
        self._volume: VolumeState = VolumeState(
            level=VolumeLevel(level=0), muted=VolumeMute(muted=False)
        )


class BangOlufsenEntity(Entity, BangOlufsenBase):
    """Base Entity for BangOlufsen entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, client: MozartClient) -> None:
        """Initialize the object."""
        super().__init__(entry, client)

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._unique_id)})
        self._attr_device_class = None
        self._attr_entity_category = None
        self._attr_should_poll = False

    async def _update_connection_state(self, connection_state: bool) -> None:
        """Update entity connection state."""
        self._attr_available = connection_state

        self.async_write_ha_state()
