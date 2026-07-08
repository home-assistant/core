"""Music Assistant Image platform."""

from datetime import datetime
import io
from typing import override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.errors import MusicAssistantError
import segno

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from . import MusicAssistantConfigEntry
from .const import LOGGER, PARTY_URL_POLL_INTERVAL
from .entity import MusicAssistantPartyModeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Image Entities."""
    mass = entry.runtime_data.mass

    def add_party_mode(instance_id: str) -> None:
        """Handle add party mode."""
        async_add_entities(
            [
                MusicAssistantPartyModeImage(
                    hass,
                    mass,
                    instance_id,
                    entity_description=ImageEntityDescription(
                        key="party_mode_qr",
                        translation_key="party_mode_qr",
                        icon="mdi:qrcode",
                    ),
                )
            ]
        )

    entry.runtime_data.party_handlers.setdefault(Platform.IMAGE, add_party_mode)


class MusicAssistantPartyModeImage(MusicAssistantPartyModeEntity, ImageEntity):
    """Representation of an Image entity for Party Mode QR Code."""

    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        mass: MusicAssistantClient,
        instance_id: str,
        entity_description: ImageEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            mass=mass,
            instance_id=instance_id,
            unique_id_suffix=entity_description.key,
            hass=hass,
        )
        self.entity_description = entity_description
        self._current_url: str | None = None
        self._image_bytes: bytes | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_timer,
                PARTY_URL_POLL_INTERVAL,
            )
        )

    async def _handle_timer(self, _now: datetime) -> None:
        """Handle periodic update."""
        await self.async_on_update()
        self.async_write_ha_state()

    @override
    async def async_on_update(self) -> None:
        """Handle provider updates."""
        try:
            url = await self.mass.send_command("party/url")
            if url != self._current_url:
                self._current_url = url
                qr = segno.make(url)
                buffer = io.BytesIO()
                qr.save(buffer, kind="png", scale=4)
                self._attr_image_last_updated = dt_util.utcnow()
                self._image_bytes = buffer.getvalue()
            self._attr_available = True
        except MusicAssistantError as err:
            LOGGER.debug("Failed to fetch party URL for QR: %s", err)
            self._current_url = None
            self._image_bytes = None
            self._attr_available = False
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Unexpected error fetching party URL for QR: %s", err)
            self._current_url = None
            self._image_bytes = None
            self._attr_available = False

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._image_bytes
