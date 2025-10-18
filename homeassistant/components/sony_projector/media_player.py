"""Media player platform for Sony Projector."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SonyProjectorConfigEntry
from .const import CONF_MODEL, CONF_SERIAL, CONF_TITLE, DEFAULT_NAME, DOMAIN
from .coordinator import SonyProjectorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player entity."""

    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator

    async_add_entities(
        [SonyProjectorMediaPlayer(entry, coordinator, runtime_data.client)]
    )


class SonyProjectorMediaPlayer(
    CoordinatorEntity[SonyProjectorCoordinator], MediaPlayerEntity
):
    """Representation of the projector as a media player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: SonyProjectorConfigEntry, coordinator, client) -> None:
        """Initialize the media player entity."""

        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]
        self._attr_unique_id = f"{identifier}-media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identifier)},
            "manufacturer": "Sony",
            "model": entry.data.get(CONF_MODEL),
            "name": entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME),
        }
        self._attr_name = None

    @property
    def available(self) -> bool:
        """Return if the projector is available."""

        return self.coordinator.last_update_success

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the power state."""

        if (data := self.coordinator.data) is None:
            return None

        return MediaPlayerState.ON if data.is_on else MediaPlayerState.OFF

    @property
    def source(self) -> str | None:
        """Return the active source."""

        return self.coordinator.data.current_input if self.coordinator.data else None

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available inputs."""

        if (data := self.coordinator.data) is None:
            return None
        return data.inputs

    async def async_turn_on(self) -> None:
        """Power on the projector."""

        await self._client.async_set_power(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Power off the projector."""

        await self._client.async_set_power(False)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select a HDMI input."""

        await self._client.async_set_input(source)
        await self.coordinator.async_request_refresh()
