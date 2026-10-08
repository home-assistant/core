"""Kodi audio and subtitle track selection."""

from typing import Any, override

from jsonrpc_base.jsonrpc import ProtocolError, TransportError

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry
from .const import DOMAIN
from .coordinator import KodiPlaybackCoordinator
from .entity import KodiPlaybackEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kodi track selectors."""
    async_add_entities(
        KodiTrackSelect(entry.runtime_data.playback, kind)
        for kind in ("audio", "subtitle")
    )


class KodiTrackSelect(KodiPlaybackEntity, SelectEntity):
    """Select a track using Kodi's stream index."""

    def __init__(self, coordinator: KodiPlaybackCoordinator, kind: str) -> None:
        """Initialize the track selector."""
        super().__init__(coordinator, f"{kind}_track")
        self.kind = kind
        self._attr_translation_key = f"{kind}_track"

    @property
    @override
    def available(self) -> bool:
        """Return whether this player supports the selector."""
        return super().available and (
            self.kind == "audio" or self.coordinator.data["player"]["type"] == "video"
        )

    def _track_options(self) -> dict[str, int]:
        """Map unique readable labels to actual stream indexes."""
        key = "audiostreams" if self.kind == "audio" else "subtitles"
        return {
            self._label(track): track["index"]
            for track in self.coordinator.data.get(key, [])
        }

    @staticmethod
    def _label(track: dict[str, Any]) -> str:
        """Include the index to distinguish tracks with identical names."""
        details = " — ".join(
            value for key in ("language", "name") if (value := track.get(key))
        )
        return f"{track['index']}: {details}" if details else str(track["index"])

    @property
    @override
    def options(self) -> list[str]:
        """Return the current stream options."""
        return (["Off"] if self.kind == "subtitle" else []) + list(
            self._track_options()
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected stream, or Off for disabled subtitles."""
        data = self.coordinator.data
        if not self.available:
            return None
        if self.kind == "subtitle" and not data.get("subtitleenabled", False):
            return "Off"
        key = "currentaudiostream" if self.kind == "audio" else "currentsubtitle"
        index = (data.get(key) or {}).get("index")
        return next(
            (
                label
                for label, stream_index in self._track_options().items()
                if stream_index == index
            ),
            None,
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Validate against fresh playback data, change the track and read it back."""
        await self.coordinator.async_refresh()
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="playback_unavailable"
            )
        options = self._track_options()
        if option not in options and not (self.kind == "subtitle" and option == "Off"):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="track_unavailable"
            )
        player_id = self.coordinator.data["player"]["playerid"]
        try:
            if self.kind == "audio":
                await self.coordinator.kodi.call_method(
                    "Player.SetAudioStream", playerid=player_id, stream=options[option]
                )
            elif option == "Off":
                await self.coordinator.kodi.call_method(
                    "Player.SetSubtitle", playerid=player_id, subtitle="off"
                )
            else:
                await self.coordinator.kodi.call_method(
                    "Player.SetSubtitle",
                    playerid=player_id,
                    subtitle=options[option],
                    enable=True,
                )
        except (TransportError, ProtocolError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="track_change_failed"
            ) from err
        await self.coordinator.async_refresh()
