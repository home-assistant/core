"""Support for the IRM KMI rain radar."""

import asyncio
import copy
from typing import TYPE_CHECKING, Any, override

from irm_kmi_api import IrmKmiApiError, RainGraph

from homeassistant.components.image import Image, ImageEntity
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TIMEZONE
from .coordinator import IrmKmiConfigEntry
from .entity import IrmKmiBaseEntity
from .utils import radar_options

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrmKmiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the image platform."""
    async_add_entities([IrmKmiRadarImage(entry)])


class IrmKmiRadarImage(IrmKmiBaseEntity, ImageEntity):
    """Animated rain radar of the next hour, rendered as an SVG."""

    _attr_content_type = "image/svg+xml"
    _attr_translation_key = "radar"
    _unrecorded_attributes = frozenset({"hint"})

    def __init__(self, entry: IrmKmiConfigEntry) -> None:
        """Create the radar image from a configuration entry."""
        super().__init__(entry)
        ImageEntity.__init__(self, self.coordinator.hass)
        self._attr_unique_id = f"{entry.data[CONF_UNIQUE_ID]}-radar"
        self._style, self._dark_mode = radar_options(entry)
        # Serialize cache misses so concurrent views share one render.
        self._lock = asyncio.Lock()
        self._animation = self.coordinator.data.animation
        self._attr_image_last_updated = self.coordinator.last_update_success_time

    @property
    @override
    def available(self) -> bool:
        """Return whether the provider published a radar loop to render."""
        return (
            super().available
            and self.coordinator.data.animation is not None
            and self.coordinator.data.country is not None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the radar hint."""
        animation = self.coordinator.data.animation
        return {"hint": animation["hint"] if animation is not None else None}

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Invalidate the cached image when the radar loop changes."""
        if self._animation != self.coordinator.data.animation:
            self._animation = self.coordinator.data.animation
            self._cached_image = None
            self._attr_image_last_updated = self.coordinator.last_update_success_time
        super()._handle_coordinator_update()

    @override
    async def async_image(self) -> bytes | None:
        """Return the animated radar SVG, rendered on first request."""
        async with self._lock:
            if self._cached_image is not None:
                return self._cached_image.content
            if (animation := self.coordinator.data.animation) is None or (
                country := self.coordinator.data.country
            ) is None:
                return None
            frames = copy.deepcopy(animation)
            tz = await dt_util.async_get_time_zone(TIMEZONE)
            if TYPE_CHECKING:
                assert tz is not None
            graph = RainGraph(
                animation_data=frames,
                country=country,
                style=self._style,
                dark_mode=self._dark_mode,
                tz=tz,
                api_client=self.coordinator.api,
            )
            try:
                content = await (await graph.build()).get_animated()
            except IrmKmiApiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="radar_unavailable",
                ) from err
            if (
                animation == self.coordinator.data.animation
                and frames["sequence"] is not None
                and all(
                    isinstance(frame["image"], bytes) for frame in frames["sequence"]
                )
            ):
                self._cached_image = Image(
                    content_type=self.content_type, content=content
                )
            return content
