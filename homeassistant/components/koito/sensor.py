"""Present normalized Koito listening data as Home Assistant sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTime

from .entity import KoitoEntity
from .models import KoitoData, MusicItem

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import KoitoConfigEntry, KoitoCoordinator

PARALLEL_UPDATES = 0


def _current_track(data: KoitoData) -> MusicItem | None:
    now_playing = data.now_playing
    return (
        now_playing.track
        if now_playing is not None and now_playing.currently_playing
        else None
    )


def _display_item(item: MusicItem | None) -> str | None:
    if item is None:
        return None
    label = item.name or item.title
    if label is None:
        return None
    if item.title is not None and item.artists:
        label = f"{', '.join(item.artists)} - {label}"
    return label[:255]


@dataclass(frozen=True, kw_only=True)
class KoitoSensorDescription(SensorEntityDescription):
    """Select a scalar value and optional music details from a typed snapshot."""

    value_fn: Callable[[KoitoData], str | int | None]
    item_fn: Callable[[KoitoData], MusicItem | None] = lambda _: None
    artist_attribute: Literal["artist", "artists"] = "artists"


SENSORS = (
    KoitoSensorDescription(
        key="plays", translation_key="plays", value_fn=lambda data: data.summary.plays
    ),
    KoitoSensorDescription(
        key="minutes_listened",
        translation_key="minutes_listened",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.summary.minutes_listened,
    ),
    KoitoSensorDescription(
        key="unique_tracks",
        translation_key="unique_tracks",
        value_fn=lambda data: data.summary.unique_tracks,
    ),
    KoitoSensorDescription(
        key="unique_albums",
        translation_key="unique_albums",
        value_fn=lambda data: data.summary.unique_albums,
    ),
    KoitoSensorDescription(
        key="unique_artists",
        translation_key="unique_artists",
        value_fn=lambda data: data.summary.unique_artists,
    ),
    KoitoSensorDescription(
        key="currently_playing_track",
        translation_key="currently_playing_track",
        value_fn=lambda data: _display_item(_current_track(data)),
        item_fn=_current_track,
        artist_attribute="artist",
    ),
    KoitoSensorDescription(
        key="top_artists",
        translation_key="top_artists",
        value_fn=lambda data: _display_item(data.top_artist),
        item_fn=lambda data: data.top_artist,
    ),
    KoitoSensorDescription(
        key="top_albums",
        translation_key="top_albums",
        value_fn=lambda data: _display_item(data.top_album),
        item_fn=lambda data: data.top_album,
    ),
    KoitoSensorDescription(
        key="top_tracks",
        translation_key="top_tracks",
        value_fn=lambda data: _display_item(data.top_track),
        item_fn=lambda data: data.top_track,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KoitoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fixed listening sensors."""
    async_add_entities(_build_entities(entry.runtime_data, entry))


def _build_entities(
    coordinator: KoitoCoordinator, entry: KoitoConfigEntry
) -> list[KoitoSensor]:
    return [KoitoSensor(coordinator, entry, description) for description in SENSORS]


class KoitoSensor(KoitoEntity, SensorEntity):
    """A view over a validated client model; no protocol parsing occurs here."""

    entity_description: KoitoSensorDescription

    def __init__(
        self,
        coordinator: KoitoCoordinator,
        entry: KoitoConfigEntry,
        description: KoitoSensorDescription,
    ) -> None:
        """Initialize a stable entity for one listening metric."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> str | int | None:
        """Read the selected scalar or formatted music label."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def _item(self) -> MusicItem | None:
        return self.entity_description.item_fn(self.coordinator.data)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Expose the artwork URL resolved by the typed adapter."""
        item = self._item
        return item.image_url if item is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose only title, artist names, and artwork for the selected item."""
        item = self._item
        if item is None:
            return {}
        attributes: dict[str, Any] = {}
        if item.title is not None:
            attributes["title"] = item.title
        if item.artists:
            key = self.entity_description.artist_attribute
            attributes[key] = (
                ", ".join(item.artists)[:255] if key == "artist" else list(item.artists)
            )
        if item.image_url is not None:
            attributes["image_url"] = item.image_url
        return attributes
