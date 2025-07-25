"""Component providing support for Reolink IP cameras."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from reolink_aio.api import DUAL_LENS_MODELS

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ReolinkChannelCoordinatorEntity, ReolinkChannelEntityDescription
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkCameraEntityDescription(
    CameraEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes camera entities for a camera channel."""

    stream: str


CAMERA_ENTITIES = (
    ReolinkCameraEntityDescription(
        key="sub",
        stream="sub",
        translation_key="sub",
        supported=lambda api, ch: api.supported(ch, "stream"),
    ),
    ReolinkCameraEntityDescription(
        key="main",
        stream="main",
        translation_key="main",
        supported=lambda api, ch: api.supported(ch, "stream"),
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="snapshots_sub",
        stream="snapshots_sub",
        translation_key="snapshots_sub",
        supported=lambda api, ch: api.supported(ch, "snapshot"),
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="snapshots",
        stream="snapshots_main",
        translation_key="snapshots_main",
        supported=lambda api, ch: api.supported(ch, "snapshot"),
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="ext",
        stream="ext",
        translation_key="ext",
        supported=lambda api, ch: api.protocol in ["rtmp", "flv"],
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="autotrack_sub",
        stream="telephoto_sub",
        translation_key="telephoto_sub",
        supported=lambda api, ch: api.supported(ch, "autotrack_stream"),
    ),
    ReolinkCameraEntityDescription(
        key="autotrack_main",
        stream="telephoto_main",
        translation_key="telephoto_main",
        supported=lambda api, ch: api.supported(ch, "autotrack_stream"),
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="autotrack_snapshots_sub",
        stream="autotrack_snapshots_sub",
        translation_key="telephoto_snapshots_sub",
        supported=lambda api, ch: api.supported(ch, "autotrack_stream"),
        entity_registry_enabled_default=False,
    ),
    ReolinkCameraEntityDescription(
        key="autotrack_snapshots_main",
        stream="autotrack_snapshots_main",
        translation_key="telephoto_snapshots_main",
        supported=lambda api, ch: api.supported(ch, "autotrack_stream"),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkCamera] = []
    for entity_description in CAMERA_ENTITIES:
        for channel in reolink_data.host.api.stream_channels:
            if not entity_description.supported(reolink_data.host.api, channel):
                continue
            stream_url = await reolink_data.host.api.get_stream_source(
                channel, entity_description.stream, False
            )
            if stream_url is None and "snapshots" not in entity_description.stream:
                continue

            entities.append(ReolinkCamera(reolink_data, channel, entity_description))

    async_add_entities(entities)


class ReolinkCamera(ReolinkChannelCoordinatorEntity, Camera):
    """An implementation of a Reolink IP camera."""

    entity_description: ReolinkCameraEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkCameraEntityDescription,
    ) -> None:
        """Initialize Reolink camera stream."""
        self.entity_description = entity_description
        ReolinkChannelCoordinatorEntity.__init__(self, reolink_data, channel)
        Camera.__init__(self)

        if "snapshots" not in entity_description.stream:
            self._attr_supported_features = CameraEntityFeature.STREAM

        if self._host.api.model in DUAL_LENS_MODELS:
            self._attr_translation_key = (
                f"{entity_description.translation_key}_lens_{self._channel}"
            )

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self._host.api.get_stream_source(
            self._channel, self.entity_description.stream
        )

    @raise_translated_error
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await self._host.api.get_snapshot(
            self._channel, self.entity_description.stream
        )
