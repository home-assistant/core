"""motionEye Media Source Implementation."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import timedelta
import logging
from pathlib import PurePath
from typing import Any, cast, override

from aiohttp import web
from motioneye_client.const import KEY_MEDIA_LIST, KEY_MIME_TYPE, KEY_PATH

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceError,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from . import split_motioneye_device_identifier
from .const import DOMAIN
from .coordinator import MotionEyeConfigEntry

MIME_TYPE_MAP = {
    "movies": "video/mp4",
    "images": "image/jpeg",
}

MEDIA_CLASS_MAP = {
    "movies": MediaClass.VIDEO,
    "images": MediaClass.IMAGE,
}

_LOGGER = logging.getLogger(__name__)

MEDIA_PROXY_URL = "/api/motioneye/media/{config_id}/{camera_id}/{kind}/{preview}/{path}"


def _encode_media_path(path: str) -> str:
    """Encode a motionEye media path for use in a Home Assistant proxy URL."""
    return urlsafe_b64encode(path.encode("utf-8")).decode("ascii")


def _build_media_proxy_path(
    config_id: str,
    camera_id: int,
    kind: str,
    path: str,
    *,
    preview: bool,
) -> str:
    """Build an authenticated Home Assistant proxy path for motionEye media."""
    return MEDIA_PROXY_URL.format(
        config_id=config_id,
        camera_id=camera_id,
        kind=kind,
        preview="1" if preview else "0",
        path=_encode_media_path(path),
    )


class MotionEyeMediaProxyView(HomeAssistantView):
    """Proxy saved motionEye media through Home Assistant."""

    requires_auth = True
    url = MEDIA_PROXY_URL
    name = "api:motioneye_media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the proxy."""
        self.hass = hass

    async def get(
        self,
        request: web.Request,
        config_id: str,
        camera_id: str,
        kind: str,
        preview: str,
        path: str,
    ) -> web.Response:
        """Return saved media fetched with the authenticated motionEye session."""
        entry = self.hass.config_entries.async_get_entry(config_id)
        if not entry or entry.state is not ConfigEntryState.LOADED:
            return web.Response(status=404)

        if kind not in MIME_TYPE_MAP:
            return web.Response(status=400)

        try:
            media_path = urlsafe_b64decode(path.encode("ascii")).decode("utf-8")
            camera = int(camera_id)
        except ValueError, UnicodeDecodeError:
            return web.Response(status=400)

        data = await cast(Any, entry.runtime_data.client).async_get_media(
            camera,
            media_path,
            image=kind == "images",
            preview=preview == "1",
        )

        return web.Response(body=data, content_type=MIME_TYPE_MAP[kind])


# Hierarchy:
#
# url (e.g. http://my-motioneye-1, http://my-motioneye-2)
# -> Camera (e.g. "Office", "Kitchen")
#   -> kind (e.g. Images, Movies)
#     -> path hierarchy as configured on motionEye


async def async_get_media_source(hass: HomeAssistant) -> MotionEyeMediaSource:
    """Set up motionEye media source."""
    hass.http.register_view(MotionEyeMediaProxyView(hass))
    return MotionEyeMediaSource(hass)


class MotionEyeMediaSource(MediaSource):
    """Provide motionEye stills and videos as media sources."""

    name: str = "motionEye Media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize MotionEyeMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        config_id, device_id, kind, path = self._parse_identifier(item.identifier)

        if not config_id or not device_id or not kind or not path:
            raise Unresolvable(
                f"Incomplete media identifier specified: {item.identifier}"
            )

        config = self._get_config_or_raise(config_id)
        device = self._get_device_or_raise(device_id)
        self._verify_kind_or_raise(kind)

        camera_id = self._get_camera_id_or_raise(config, device)
        media_path = self._get_path_or_raise(path)
        proxy_path = _build_media_proxy_path(
            config.entry_id,
            camera_id,
            kind,
            media_path,
            preview=False,
        )
        url = async_sign_path(
            self.hass,
            proxy_path,
            timedelta(minutes=5),
            use_content_user=True,
        )
        return PlayMedia(url, MIME_TYPE_MAP[kind])

    @callback
    @classmethod
    def _parse_identifier(
        cls, identifier: str
    ) -> tuple[str | None, str | None, str | None, str | None]:
        base = [None] * 4
        data = identifier.split("#", 3)
        return cast(
            tuple[str | None, str | None, str | None, str | None],
            tuple(data + base)[:4],  # type: ignore[operator]
        )

    @override
    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            config_id, device_id, kind, path = self._parse_identifier(item.identifier)
            config = device = None
            if config_id:
                config = self._get_config_or_raise(config_id)
            if device_id:
                device = self._get_device_or_raise(device_id)
            if kind:
                self._verify_kind_or_raise(kind)
            path = self._get_path_or_raise(path)

            if config and device and kind:
                return await self._build_media_path(config, device, kind, path)
            if config and device:
                return self._build_media_kinds(config, device)
            if config:
                return self._build_media_devices(config)
        return self._build_media_configs()

    def _get_config_or_raise(self, config_id: str) -> MotionEyeConfigEntry:
        """Get a config entry from a URL."""
        entry = self.hass.config_entries.async_get_entry(config_id)
        if not entry or entry.state is not ConfigEntryState.LOADED:
            raise MediaSourceError(f"Unable to find config entry with id: {config_id}")
        return entry

    def _get_device_or_raise(self, device_id: str) -> dr.DeviceEntry:
        """Get a config entry from a URL."""
        device_registry = dr.async_get(self.hass)
        if not (
            device := device_registry.async_get(device_id, include_child_devices=False)
        ):
            raise MediaSourceError(f"Unable to find device with id: {device_id}")
        return device

    @classmethod
    def _verify_kind_or_raise(cls, kind: str) -> None:
        """Verify kind is an expected value."""
        if kind in MEDIA_CLASS_MAP:
            return
        raise MediaSourceError(f"Unknown media type: {kind}")

    @classmethod
    def _get_path_or_raise(cls, path: str | None) -> str:
        """Verify path is a valid motionEye path."""
        if not path:
            return "/"
        if PurePath(path).root == "/":
            return path
        raise MediaSourceError(
            f"motionEye media path must start with '/', received: {path}"
        )

    @classmethod
    def _get_camera_id_or_raise(
        cls, config: MotionEyeConfigEntry, device: dr.DeviceEntry
    ) -> int:
        """Get a config entry from a URL."""
        for identifier in device.identifiers:
            data = split_motioneye_device_identifier(identifier)
            if data is not None:
                return data[2]
        raise MediaSourceError(f"Could not find camera id for device id: {device.id}")

    @classmethod
    def _build_media_config(cls, config: MotionEyeConfigEntry) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=config.entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=config.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_media_configs(self) -> BrowseMediaSource:
        """Build the media sources for config entries."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title="motionEye Media",
            can_play=False,
            can_expand=True,
            children=[
                self._build_media_config(entry)
                for entry in self.hass.config_entries.async_entries(DOMAIN)
            ],
            children_media_class=MediaClass.DIRECTORY,
        )

    @classmethod
    def _build_media_device(
        cls,
        config: MotionEyeConfigEntry,
        device: dr.DeviceEntry,
        full_title: bool = True,
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{config.entry_id}#{device.id}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"{config.title} {device.name}" if full_title else device.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_media_devices(self, config: MotionEyeConfigEntry) -> BrowseMediaSource:
        """Build the media sources for device entries."""
        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(device_registry, config.entry_id)

        base = self._build_media_config(config)
        base.children = [
            self._build_media_device(config, device, full_title=False)
            for device in devices
        ]
        return base

    @classmethod
    def _build_media_kind(
        cls,
        config: MotionEyeConfigEntry,
        device: dr.DeviceEntry,
        kind: str,
        full_title: bool = True,
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{config.entry_id}#{device.id}#{kind}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=(
                MediaType.VIDEO if kind == "movies" else MediaType.IMAGE
            ),
            title=(
                f"{config.title} {device.name} {kind.title()}"
                if full_title
                else kind.title()
            ),
            can_play=False,
            can_expand=True,
            children_media_class=(
                MediaClass.VIDEO if kind == "movies" else MediaClass.IMAGE
            ),
        )

    def _build_media_kinds(
        self, config: MotionEyeConfigEntry, device: dr.DeviceEntry
    ) -> BrowseMediaSource:
        base = self._build_media_device(config, device)
        base.children = [
            self._build_media_kind(config, device, kind, full_title=False)
            for kind in MEDIA_CLASS_MAP
        ]
        return base

    async def _build_media_path(
        self,
        config: MotionEyeConfigEntry,
        device: dr.DeviceEntry,
        kind: str,
        path: str,
    ) -> BrowseMediaSource:
        """Build the media sources for media kinds."""
        base = self._build_media_kind(config, device, kind)

        parsed_path = PurePath(path)
        if path != "/":
            base.title += f" {PurePath(*parsed_path.parts[1:])}"

        base.children = []

        client = config.runtime_data.client
        camera_id = self._get_camera_id_or_raise(config, device)

        if kind == "movies":
            resp = await client.async_get_movies(camera_id)
        else:
            resp = await client.async_get_images(camera_id)

        sub_dirs: set[str] = set()
        parts = parsed_path.parts
        media_list = resp.get(KEY_MEDIA_LIST, []) if resp else []

        def get_media_sort_key(media: dict) -> str:
            """Get media sort key."""
            return media.get(KEY_PATH, "")

        for media in sorted(media_list, key=get_media_sort_key):
            if (
                KEY_PATH not in media
                or KEY_MIME_TYPE not in media
                or media[KEY_MIME_TYPE] not in MIME_TYPE_MAP.values()
            ):
                continue

            # Example path: '/2021-04-21/21-13-10.mp4'
            parts_media = PurePath(media[KEY_PATH]).parts

            if parts_media[: len(parts)] == parts and len(parts_media) > len(parts):
                full_child_path = str(PurePath(*parts_media[: len(parts) + 1]))
                display_child_path = parts_media[len(parts)]

                # Child is a media file.
                if len(parts) + 1 == len(parts_media):
                    thumbnail_path = _build_media_proxy_path(
                        config.entry_id,
                        camera_id,
                        kind,
                        full_child_path,
                        preview=True,
                    )
                    thumbnail_url = async_sign_path(
                        self.hass,
                        thumbnail_path,
                        timedelta(minutes=5),
                        use_content_user=True,
                    )

                    base.children.append(
                        BrowseMediaSource(
                            domain=DOMAIN,
                            identifier=f"{config.entry_id}#{device.id}#{kind}#{full_child_path}",
                            media_class=MEDIA_CLASS_MAP[kind],
                            media_content_type=media[KEY_MIME_TYPE],
                            title=display_child_path,
                            can_play=(kind == "movies"),
                            can_expand=False,
                            thumbnail=thumbnail_url,
                        )
                    )

                # Child is a subdirectory.
                elif len(parts) + 1 < len(parts_media):
                    if full_child_path not in sub_dirs:
                        sub_dirs.add(full_child_path)
                        base.children.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=(
                                    f"{config.entry_id}#{device.id}"
                                    f"#{kind}#{full_child_path}"
                                ),
                                media_class=MediaClass.DIRECTORY,
                                media_content_type=(
                                    MediaType.VIDEO
                                    if kind == "movies"
                                    else MediaType.IMAGE
                                ),
                                title=display_child_path,
                                can_play=False,
                                can_expand=True,
                                children_media_class=MediaClass.DIRECTORY,
                            )
                        )
        return base
