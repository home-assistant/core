"""Support for iCloud album cameras."""

from copy import deepcopy
import datetime
import logging
import random
from typing import Any

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud.services.photos import (
    AlbumContainer,
    BasePhotoAlbum,
    PhotoAsset,
    PhotoStreamAsset,
)

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, DeviceRegistry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_ALBUM_ID,
    CONF_ALBUM_NAME,
    CONF_ALBUM_TYPE,
    CONF_PICTURE_INTERVAL,
    CONF_RANDOM_ORDER,
    DEFAULT_PICTURE_INTERVAL,
    DEFAULT_RANDOM_ORDER,
    DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cameras from subentries."""

    api: PyiCloudService = entry.runtime_data.api

    device_registry: DeviceRegistry = dr.async_get(hass)
    for subentry in entry.subentries.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry.subentry_id,
            identifiers={
                (DOMAIN, f"{subentry.subentry_id}"),
                (DOMAIN, subentry.data[CONF_ALBUM_ID]),
            },
            configuration_url="https://www.icloud.com/",
            manufacturer="Apple",
            name=f"iCloud Album - {subentry.data[CONF_ALBUM_NAME]}",
            model="Apple iCloud Photo Album"
            if subentry.data.get(CONF_ALBUM_TYPE) == "album"
            else "Apple iCloud Shared Stream",
        )

    entities: list[AppleiCloudAlbumCamera] = [
        AppleiCloudAlbumCamera(api, entry, subentry)
        for subentry in entry.subentries.values()
        if subentry.data.get(CONF_ALBUM_TYPE) == "album"
    ] + [
        AppleiCloudSharedStreamCamera(api, entry, subentry)
        for subentry in entry.subentries.values()
        if subentry.data.get(CONF_ALBUM_TYPE) == "shared_stream"
    ]

    async_add_entities(
        entities,
        False,
    )


class AppleiCloudAlbumCamera(Camera):
    """Representation of an iCloud album camera."""

    _attr_model = "Apple iCloud Photo Album"
    _attr_brand = "Apple"
    _attr_has_entity_name = False
    _attr_icon = "mdi:image"

    def __init__(
        self, api: PyiCloudService, config_entry: ConfigEntry, sub_entry: ConfigSubentry
    ) -> None:
        """Initialize iCloud album camera."""
        super().__init__()
        self._api: PyiCloudService | None = api
        self._config_entry: ConfigEntry = config_entry
        self._subentry: ConfigSubentry = sub_entry

        self._id: str = sub_entry.data[CONF_ALBUM_ID]
        self._type: str = sub_entry.data[CONF_ALBUM_TYPE]
        self._random: bool = sub_entry.data.get(CONF_RANDOM_ORDER, DEFAULT_RANDOM_ORDER)

        self._attr_unique_id = f"{self._type}_{self._id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sub_entry.data[CONF_ALBUM_ID])},
            configuration_url="https://www.icloud.com/",
            manufacturer="Apple",
            name=f"iCloud Album - {sub_entry.data[CONF_ALBUM_NAME]}",
            model="Apple iCloud Photo Album"
            if self._type == "album"
            else "Apple iCloud Shared Stream",
        )

        self._current_photo_index: int = sub_entry.data.get("current_photo_index", 0)
        self._album: BasePhotoAlbum | None = None
        self._photo: PhotoAsset | None = None
        self._image: bytes | None = None
        self._attr_available: bool = False

    def _get_album(self) -> None:
        """Get the album."""
        if self._api is None:
            return
        try:
            if self._type == "album":
                albums: AlbumContainer = self._api.photos.albums
            else:
                albums = self._api.photos.shared_streams
        except PyiCloudServiceNotActivatedException as exc:
            _LOGGER.error("Apple iCloud Photos service is not activated: %s", exc)
            return
        self._album = albums.get(self._id)
        self._next_image()

    async def _load_album(self) -> None:
        await self.hass.async_add_executor_job(self._get_album)
        if self._album is None:
            self._attr_available = False
            return

        self._attr_name = f"{self._album.title} Album"
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        _LOGGER.debug("Adding iCloud album camera: %s", self._id)
        await super().async_added_to_hass()
        self.hass.async_create_task(self._load_album())

        interval: float = self._subentry.data.get(
            CONF_PICTURE_INTERVAL, DEFAULT_PICTURE_INTERVAL
        )

        if interval == 0.0:
            return

        self.async_on_remove(
            async_track_time_interval(
                hass=self.hass,
                action=self._handle_timer_update,
                interval=datetime.timedelta(seconds=interval),
                name=self.entity_id,
                cancel_on_shutdown=True,
            )
        )

    async def _handle_timer_update(self, _) -> None:
        """Handle the update timer."""
        await self.next_image()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self._attr_available
            and self._api is not None
            and self._album is not None
            and self._photo is not None
            and self._image is not None
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes:
        """Return bytes of camera image."""
        if not self.enabled or self._album is None or self._attr_is_on is False:
            return b""
        return self._image or b""

    async def next_image(self, randomize: bool | None = None) -> None:
        """Load the next image."""
        if not self.enabled or self._album is None or self._attr_is_on is False:
            return
        self.hass.add_job(self._next_image, randomize)

    def _next_image(self, randomize: bool | None = None) -> None:
        """Load the next image."""
        _LOGGER.debug("Loading next image")
        if self._album is None:
            return

        num_photos: int = len(self._album)

        if num_photos == 0:
            return

        if randomize or (randomize is None and self._random):
            self.current_photo_index = random.randint(0, num_photos - 1)
        else:
            self.current_photo_index += 1
            if self.current_photo_index >= num_photos:
                self.current_photo_index = 0
        try:
            photo: PhotoAsset = self._album.photo(self.current_photo_index)
            self._photo = photo
            self._image = self._photo.download()
        except PyiCloudAPIResponseException as exc:
            _LOGGER.error(
                "Error loading photo at index %d: %s", self.current_photo_index, exc
            )
            return

        if self._photo is None:
            return

        self.hass.add_job(self.async_write_ha_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self._photo is None:
            return {}

        return {
            "photo_id": self._photo.id,
            "created": self._photo.created,
            "is_live_photo": self._photo.is_live_photo,
            "dimensions": f"{self._photo.dimensions[0]}x{self._photo.dimensions[1]}",
            "filename": self._photo.filename,
            "total_photos": len(self._album) if self._album else 0,
            "picture_type": self._photo.item_type,
        }

    @callback
    def _update_entry(self) -> None:
        """Update the config entry to persist the current photo index."""
        if self._album is None:
            return
        self.hass.config_entries.async_update_subentry(
            entry=self._config_entry,
            subentry=self._subentry,
            data={
                **self._subentry.data,
                "current_photo_index": self._current_photo_index,
            },
        )

    @property
    def current_photo_index(self) -> int:
        """Return the current photo index."""
        return self._current_photo_index

    @current_photo_index.setter
    def current_photo_index(self, value: int) -> None:
        """Set the current photo index."""
        self._current_photo_index = value
        self.hass.add_job(self._update_entry)

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        self._attr_is_on = True
        self.async_write_ha_state()


class AppleiCloudSharedStreamCamera(AppleiCloudAlbumCamera):
    """Representation of an iCloud shared stream camera."""

    _attr_model: str = "Apple iCloud Shared Stream"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] | None = super().extra_state_attributes
        if self._photo is None or not attrs:
            return {}

        if isinstance(self._photo, PhotoStreamAsset):
            attrs = deepcopy(attrs)
            attrs.update(
                {
                    "like_count": self._photo.like_count,
                    "liked": self._photo.liked,
                }
            )
        return attrs
