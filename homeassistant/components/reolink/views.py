"""Reolink Integration views."""

import asyncio
from collections import defaultdict
from datetime import datetime
from http import HTTPStatus
import logging
import secrets

from aiohttp import web
from reolink_aio.baichuan.media_decoder import HLS_PLAYLIST
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant, callback

from .util import get_host

_LOGGER = logging.getLogger(__name__)

# Each thumbnail costs a Baichuan request and an ffmpeg decode.
MAX_PARALLEL_THUMBNAILS = 2
THUMBNAIL_STREAMS = {"sub", "telephoto_sub"}
TELEPHOTO_PREFIXES = ("autotrack_", "telephoto_")


@callback
def async_generate_playback_proxy_url(config_entry_id: str, token: str) -> str:
    """Generate the URL of the HLS playlist of a recording being downloaded."""
    return PlaybackProxyView.url.format(
        config_entry_id=config_entry_id, token=token, filename=HLS_PLAYLIST
    )


@callback
def async_generate_thumbnail_url(
    config_entry_id: str, channel: int, stream: str, time_id: str
) -> str:
    """Generate URL for the thumbnail of a recording."""
    return ThumbnailView.url.format(
        config_entry_id=config_entry_id,
        channel=channel,
        stream="telephoto_sub" if stream.startswith(TELEPHOTO_PREFIXES) else "sub",
        time_id=time_id,
    )


class PlaybackProxyView(HomeAssistantView):
    """View to serve the HLS files of a Reolink recording being downloaded."""

    # The HLS player does not authenticate the requests for the files in the
    # playlist, the random token of the playback is used instead.
    requires_auth = False
    url = "/api/reolink/hls/{config_entry_id}/{token}/{filename}"
    name = "api:reolink_hls"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the HLS view."""
        self.hass = hass

    async def get(
        self, request: web.Request, config_entry_id: str, token: str, filename: str
    ) -> web.FileResponse:
        """Return a HLS file, wait for it when it is not downloaded yet."""
        try:
            playback = get_host(self.hass, config_entry_id).hls_playback
        except Unresolvable:
            playback = None
        if playback is None or not secrets.compare_digest(playback.token, token):
            raise web.HTTPNotFound

        path = await playback.async_get_file(filename)
        if path is None:
            raise web.HTTPNotFound

        if filename == HLS_PLAYLIST:
            content_type = "application/vnd.apple.mpegurl"
        else:
            content_type = "video/mp4"
        return web.FileResponse(path, headers={"Content-Type": content_type})


class ThumbnailView(HomeAssistantView):
    """View to get a thumbnail of a Reolink recording."""

    requires_auth = True
    url = "/api/reolink/thumbnail/{config_entry_id}/{channel}/{stream}/{time_id}"
    name = "api:reolink_thumbnail"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a thumbnail view."""
        self.hass = hass
        self._semaphores: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(MAX_PARALLEL_THUMBNAILS)
        )

    async def get(
        self,
        request: web.Request,
        config_entry_id: str,
        channel: str,
        stream: str,
        time_id: str,
    ) -> web.Response:
        """Get the key frame at a moment in a recording as JPEG."""
        try:
            get_host(self.hass, config_entry_id)
        except Unresolvable:
            return self._unknown_config_entry(config_entry_id)

        try:
            ch = int(channel)
            time = datetime.strptime(time_id, "%Y%m%d%H%M%S")
        except ValueError:
            err_str = f"Reolink thumbnail invalid channel {channel} or time {time_id}"
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        if stream not in THUMBNAIL_STREAMS:
            err_str = f"Reolink thumbnail invalid stream {stream}"
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        async with self._semaphores[config_entry_id]:
            # The config entry can be unloaded or reloaded while waiting.
            try:
                host = get_host(self.hass, config_entry_id)
            except Unresolvable:
                return self._unknown_config_entry(config_entry_id)

            if not host.api.supported(ch, "sub"):
                stream = stream.replace("sub", "main")

            try:
                image = await host.api.baichuan.snapshot_past(
                    ch,
                    time,
                    stream,
                    get_ffmpeg_manager(self.hass).binary,
                )
            except ReolinkError as err:
                _LOGGER.debug(
                    "Error getting thumbnail of channel %s at %s: %s",
                    ch,
                    time_id,
                    err,
                )
                return web.Response(body=str(err), status=HTTPStatus.BAD_REQUEST)

        # Recordings do not change, so the thumbnail can be cached.
        return web.Response(
            body=image,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=2592000"},
        )

    @staticmethod
    def _unknown_config_entry(config_entry_id: str) -> web.Response:
        """Return the response for an unknown or unloaded config entry."""
        _LOGGER.debug(
            "Thumbnail requested for unknown config entry %s", config_entry_id
        )
        err_str = f"Reolink thumbnail could not find config entry id: {config_entry_id}"
        return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)
