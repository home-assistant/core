"""Current Kodi stream and picture information."""

from typing import Any, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry
from .coordinator import KodiPlaybackCoordinator
from .entity import KodiPlaybackEntity


class KodiStreamSensorDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describe a field in a Kodi stream or playback state."""

    stream: str | None = None
    field: str | None = None
    coordinator_key: str | None = None


SENSORS = (
    KodiStreamSensorDescription(
        key="chapter_name",
        translation_key="chapter_name",
        coordinator_key="chapter_name",
    ),
    KodiStreamSensorDescription(
        key="chapter_number",
        translation_key="chapter_number",
        coordinator_key="chapter_number",
    ),
    KodiStreamSensorDescription(
        key="chapter_count",
        translation_key="chapter_count",
        coordinator_key="chapter_count",
    ),
    KodiStreamSensorDescription(
        key="video_codec",
        translation_key="video_codec",
        stream="currentvideostream",
        field="codec",
    ),
    KodiStreamSensorDescription(
        key="video_width",
        translation_key="video_width",
        stream="currentvideostream",
        field="width",
        native_unit_of_measurement="px",
    ),
    KodiStreamSensorDescription(
        key="video_height",
        translation_key="video_height",
        stream="currentvideostream",
        field="height",
        native_unit_of_measurement="px",
    ),
    KodiStreamSensorDescription(
        key="video_fps",
        translation_key="video_fps",
        coordinator_key="video_fps",
        native_unit_of_measurement="fps",
    ),
    KodiStreamSensorDescription(
        key="video_hdr_type",
        translation_key="video_hdr_type",
        coordinator_key="video_hdr_type",
    ),
    KodiStreamSensorDescription(
        key="picture_view_mode",
        translation_key="picture_view_mode",
        coordinator_key="viewmode",
    ),
    KodiStreamSensorDescription(
        key="audio_codec",
        translation_key="audio_codec",
        stream="currentaudiostream",
        field="codec",
    ),
    KodiStreamSensorDescription(
        key="audio_channels",
        translation_key="audio_channels",
        stream="currentaudiostream",
        field="channels",
    ),
    KodiStreamSensorDescription(
        key="audio_language",
        translation_key="audio_language",
        stream="currentaudiostream",
        field="language",
    ),
    KodiStreamSensorDescription(
        key="audio_delay",
        translation_key="audio_delay",
        coordinator_key="audio_delay",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=3,
    ),
    KodiStreamSensorDescription(
        key="subtitle_delay",
        translation_key="subtitle_delay",
        coordinator_key="subtitle_delay",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kodi stream sensors."""
    async_add_entities(
        KodiStreamSensor(entry.runtime_data.playback, description)
        for description in SENSORS
    )


class KodiStreamSensor(KodiPlaybackEntity, SensorEntity):
    """Expose information about the currently selected stream or video."""

    entity_description: KodiStreamSensorDescription

    def __init__(
        self,
        coordinator: KodiPlaybackCoordinator,
        description: KodiStreamSensorDescription,
    ) -> None:
        """Initialize a stream sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Require reported delay values for the playback delay sensors."""
        if self.entity_description.coordinator_key in (
            "audio_delay",
            "subtitle_delay",
        ):
            return (
                super().available
                and self.coordinator.data.get(self.entity_description.coordinator_key)
                is not None
            )
        return super().available

    @property
    @override
    def native_value(self) -> str | int | float | None:
        """Return a field when supported by this Kodi version."""
        description = self.entity_description
        if description.stream is not None and description.field is not None:
            stream: dict[str, Any] = self.coordinator.data.get(description.stream) or {}
            return stream.get(description.field)
        if description.coordinator_key == "viewmode":
            viewmode = self.coordinator.data.get("viewmode") or {}
            return viewmode.get("viewmode")
        value = self.coordinator.data.get(description.coordinator_key or "")
        if description.coordinator_key == "video_hdr_type" and isinstance(value, str):
            return {
                "dolbyvision": "Dolby Vision",
                "hdr10": "HDR10",
                "hlg": "HLG",
                "sdr": "SDR",
            }.get(value, value.upper())
        return value if isinstance(value, (str, int, float)) else None
