"""Sensor platform for FMD integration."""

from datetime import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

if TYPE_CHECKING:
    from fmd_api import FmdClient  # pragma: no cover

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FMD sensor entities."""
    api: FmdClient = entry.runtime_data.api
    device_info = entry.runtime_data.device_info

    sensors = [
        FmdPhotoCountSensor(hass, entry, api, device_info),
    ]

    async_add_entities(sensors)

    # Store sensor reference for download button to access
    entry.runtime_data.photo_count_sensor = sensors[0]


class FmdPhotoCountSensor(SensorEntity):
    """Sensor that tracks the number of photos available."""

    _attr_has_entity_name = True
    _attr_name = "Photo count"
    _attr_native_unit_of_measurement = "photos"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: FmdClient,
        device_info: dict,
    ) -> None:
        """Initialize the photo count sensor."""
        self.hass = hass
        self.entry = entry
        self.api = api
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_photo_count"

        # Restore state from config entry if present
        data = entry.data
        self._photos_in_media_folder = data.get("photo_count_photos_in_media_folder", 0)
        self._last_download_count = data.get("photo_count_last_download_count", 0)
        last_time = data.get("photo_count_last_download_time")
        self._last_download_time: datetime | None
        if last_time:
            try:
                self._last_download_time = datetime.fromisoformat(last_time)
            except Exception:  # noqa: BLE001
                self._last_download_time = None
        else:
            self._last_download_time = None

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:image-multiple"

    @property
    def native_value(self) -> int:
        """Return the total number of photos stored in media folder."""
        return self._photos_in_media_folder

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        return {
            "last_download_count": self._last_download_count,
            "last_download_time": (
                self._last_download_time.isoformat()
                if self._last_download_time
                else None
            ),
            "photos_in_media_folder": self._photos_in_media_folder,  # Keep for
            # backward compatibility
        }

    def update_photo_count(self, download_count: int) -> None:
        """Update the photo count after a download and persist state."""
        self._last_download_count = download_count
        self._last_download_time = datetime.now()
        self._update_media_folder_count()

        # Persist state to config entry
        new_data = dict(self.entry.data)
        new_data["photo_count_photos_in_media_folder"] = self._photos_in_media_folder
        new_data["photo_count_last_download_count"] = self._last_download_count
        new_data["photo_count_last_download_time"] = (
            self._last_download_time.isoformat() if self._last_download_time else None
        )
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    def _update_media_folder_count(self) -> None:
        """Count photos in the media folder."""
        try:
            # Check /media first (Docker/Core), fall back to config/media (HAOS)
            media_base = Path("/media")
            if not media_base.exists() or not media_base.is_dir():
                media_base = Path(self.hass.config.path("media"))

            # Use device-specific subdirectory
            device_id = self.entry.data["id"]
            media_dir = media_base / "fmd" / device_id

            if media_dir.exists():
                self._photos_in_media_folder = len(list(media_dir.glob("*.jpg")))
            else:
                self._photos_in_media_folder = 0
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to count media folder photos: %s", e)
            self._photos_in_media_folder = 0
