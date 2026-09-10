"""Reolink Integration views."""

import asyncio
from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextlib import aclosing, suppress
from enum import Enum, auto
import hashlib
from http import HTTPStatus
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import IO, Any

from aiohttp import ClientError, ClientTimeout, web
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import SSLCipherList

from .host import ReolinkHost
from .util import get_host

_LOGGER = logging.getLogger(__name__)

VOD_CACHE_DIR = "reolink_vod"
VOD_CACHE_MAX_AGE = 3600.0
VOD_CACHE_MAX_BYTES = 2 * 1024**3
VOD_WRITE_BUFFER = 4 * 1024**2
VOD_CACHE_GRACE = 60.0


class _CacheState(Enum):
    """What a request can do with the recording it asked for."""

    CACHED = auto()
    DOWNLOAD = auto()
    FULL = auto()


def _open_part(cache_dir: Path) -> tuple[IO[bytes], Path]:
    """Create the temporary file a recording is downloaded into."""
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=cache_dir, suffix=".part")
    return os.fdopen(descriptor, "wb"), Path(name)


def _discard_part(handle: IO[bytes], part: Path) -> None:
    """Close and remove a partially downloaded recording, never raising."""
    with suppress(OSError):
        handle.close()
    with suppress(OSError):
        part.unlink(missing_ok=True)


def _finish_part(handle: IO[bytes], part: Path, path: Path) -> bool:
    """Move a completed download into the cache."""
    try:
        handle.close()
        part.replace(path)
    except OSError:
        _discard_part(handle, part)
        return False
    return True


def _prepare_cache(path: Path, size: int, serving: set[Path]) -> _CacheState:
    """Prune the cache and report what can be done with this recording."""
    now = time.time()
    try:
        stat = path.stat()
    except OSError:
        pass
    else:
        if stat.st_size == size and now - stat.st_mtime <= VOD_CACHE_MAX_AGE:
            return _CacheState.CACHED
        with suppress(OSError):
            path.unlink(missing_ok=True)

    if _prune_cache(path.parent, size, serving):
        return _CacheState.DOWNLOAD
    return _CacheState.FULL


def _prune_cache(cache_dir: Path, size: int, serving: set[Path]) -> bool:
    """Drop aged out and excess recordings, reporting whether size still fits."""
    now = time.time()
    try:
        contents = list(cache_dir.iterdir())
    except OSError:
        return True

    used = 0
    entries: list[tuple[float, int, Path]] = []
    for item in contents:
        try:
            stat = item.stat()
        except OSError:
            continue
        if item.suffix == ".part":
            # only a part left behind by an interrupted download gets this old
            if now - stat.st_mtime > VOD_CACHE_MAX_AGE:
                with suppress(OSError):
                    item.unlink()
                    continue
            used += stat.st_size
            continue
        entries.append((stat.st_mtime, stat.st_size, item))

    for mtime, cached, item in sorted(
        entries, key=lambda entry: entry[0], reverse=True
    ):
        # one just handed to a response may still be on its way to a client
        expendable = item not in serving and now - mtime > VOD_CACHE_GRACE
        if expendable and (
            now - mtime > VOD_CACHE_MAX_AGE
            or used + cached + size > VOD_CACHE_MAX_BYTES
        ):
            with suppress(OSError):
                item.unlink()
                continue
        used += cached

    return used + size <= VOD_CACHE_MAX_BYTES


@callback
def async_generate_playback_proxy_url(
    config_entry_id: str, channel: int, filename: str, stream_res: str, vod_type: str
) -> str:
    """Generate proxy URL for event video."""

    url_format = PlaybackProxyView.url
    return url_format.format(
        config_entry_id=config_entry_id,
        channel=channel,
        filename=urlsafe_b64encode(filename.encode("utf-8")).decode("utf-8"),
        stream_res=stream_res,
        vod_type=vod_type,
    )


class PlaybackProxyView(HomeAssistantView):
    """View to proxy playback video from Reolink."""

    requires_auth = True
    url = (
        "/api/reolink/video"
        "/{config_entry_id}/{channel}/{stream_res}"
        "/{vod_type}/{filename}"
    )
    name = "api:reolink_playback"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a proxy view."""
        self.hass = hass
        self.session = async_get_clientsession(
            hass,
            verify_ssl=False,
            ssl_cipher=SSLCipherList.INSECURE,
        )
        self._vod_type: str | None = None
        self._vod_locks: dict[str, asyncio.Lock] = {}
        self._vod_cache_lock = asyncio.Lock()
        self._vod_serving: dict[Path, float] = {}

    async def get(
        self,
        request: web.Request,
        config_entry_id: str,
        channel: str,
        stream_res: str,
        vod_type: str,
        filename: str,
        retry: int = 2,
    ) -> web.StreamResponse:
        """Get playback proxy video response."""
        retry = retry - 1

        filename_decoded = urlsafe_b64decode(filename.encode("utf-8")).decode("utf-8")
        ch = int(channel)
        # this has to be read before the remembered type overrides it below
        nvr_download = VodRequestType(vod_type) is VodRequestType.NVR_DOWNLOAD
        if self._vod_type is not None:
            vod_type = self._vod_type
        try:
            host = get_host(self.hass, config_entry_id)
        except Unresolvable:
            err_str = (
                "Reolink playback proxy could not find"
                f" config entry id: {config_entry_id}"
            )
            _LOGGER.warning(err_str)
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        # an NVR download asks for a time range rather than a stored file
        if not nvr_download:
            baichuan_response = await self._async_serve_vod_over_baichuan(
                config_entry_id, host, ch, stream_res, filename_decoded
            )
            if baichuan_response is not None:
                return baichuan_response

        try:
            _mime_type, reolink_url = await host.api.get_vod_source(
                ch, filename_decoded, stream_res, VodRequestType(vod_type)
            )
        except ReolinkError as err:
            _LOGGER.warning("Reolink playback proxy error: %s", str(err))
            return web.Response(body=str(err), status=HTTPStatus.BAD_REQUEST)

        headers = dict(request.headers)
        headers.pop("Host", None)
        headers.pop("Referer", None)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Requested Playback Proxy Method %s, Headers: %s",
                request.method,
                headers,
            )
            _LOGGER.debug(
                "Opening VOD stream from %s: %s",
                host.api.camera_name(ch),
                host.api.hide_password(reolink_url),
            )

        try:
            reolink_response = await self.session.get(
                reolink_url,
                headers=headers,
                timeout=ClientTimeout(
                    connect=15, sock_connect=15, sock_read=5, total=None
                ),
            )
        except ClientError as err:
            err_str = host.api.hide_password(
                f"Reolink playback error while getting mp4: {err!s}"
            )
            if retry <= 0:
                _LOGGER.warning(err_str)
                return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)
            _LOGGER.debug("%s, renewing token", err_str)
            await host.api.expire_session(unsubscribe=False)
            return await self.get(
                request, config_entry_id, channel, stream_res, vod_type, filename, retry
            )

        # Reolink typo "apolication/octet-stream" instead of "application/octet-stream"
        if reolink_response.content_type not in [
            "video/mp4",
            "application/octet-stream",
            "apolication/octet-stream",
        ]:
            err_str = (
                "Reolink playback expected video/mp4"
                f" but got {reolink_response.content_type}"
            )
            if (
                reolink_response.content_type == "video/x-flv"
                and vod_type == VodRequestType.PLAYBACK.value
            ):
                # next time use DOWNLOAD immediately
                self._vod_type = VodRequestType.DOWNLOAD.value
                _LOGGER.debug(
                    "%s, retrying using download instead of playback cmd", err_str
                )
                return await self.get(
                    request,
                    config_entry_id,
                    channel,
                    stream_res,
                    self._vod_type,
                    filename,
                    retry,
                )

            _LOGGER.error(err_str)
            if reolink_response.content_type == "text/html":
                text = await reolink_response.text()
                _LOGGER.debug(text)
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        response_headers = dict(reolink_response.headers)
        _LOGGER.debug(
            "Response Playback Proxy Status %s:%s, Headers: %s",
            reolink_response.status,
            reolink_response.reason,
            response_headers,
        )
        if "Content-Type" not in response_headers:
            response_headers["Content-Type"] = reolink_response.content_type
        if response_headers["Content-Type"] == "apolication/octet-stream":
            response_headers["Content-Type"] = "application/octet-stream"

        response = web.StreamResponse(
            status=reolink_response.status,
            reason=reolink_response.reason,
            headers=response_headers,
        )

        await response.prepare(request)

        try:
            async for chunk in reolink_response.content.iter_chunked(65536):
                await response.write(chunk)
        except TimeoutError:
            _LOGGER.debug(
                "Timeout while reading Reolink playback from %s, writing EOF",
                host.api.nvr_name,
            )
        finally:
            reolink_response.release()

        await response.write_eof()
        return response

    async def _async_serve_vod_over_baichuan(
        self,
        config_entry_id: str,
        host: ReolinkHost,
        channel: int,
        stream: str,
        filename: str,
    ) -> web.StreamResponse | None:
        """Serve a recording fetched over Baichuan, or None to fall back to HTTP."""
        cache_dir = Path(self.hass.config.cache_path(VOD_CACHE_DIR))
        key = f"{config_entry_id}|{channel}|{stream}|{filename}".encode()
        path = cache_dir / f"{hashlib.sha256(key).hexdigest()[:32]}.mp4"

        # one Baichuan VOD session per host, claimed by asking as well as downloading
        lock = self._vod_locks.setdefault(config_entry_id, asyncio.Lock())
        async with lock:
            try:
                info = await host.api.baichuan.get_vod_file_info(
                    channel, filename, stream
                )
            except ReolinkError as err:
                _LOGGER.debug(
                    "Reolink %s cannot fetch %s over Baichuan, using HTTP playback: %s",
                    host.api.nvr_name,
                    filename,
                    err,
                )
                return None

            if info.size > VOD_CACHE_MAX_BYTES:
                _LOGGER.debug(
                    "Reolink %s recording %s is too large to cache,"
                    " using HTTP playback",
                    host.api.nvr_name,
                    filename,
                )
                return None

            # pruning runs in the executor, so another config entry could delete
            # this recording between it being accepted and the claim below
            async with self._vod_cache_lock:
                state = await self.hass.async_add_executor_job(
                    _prepare_cache, path, info.size, self._async_vod_serving()
                )
                # aiohttp opens the file only after this handler returns
                self._vod_serving[path] = time.monotonic()

            if state is _CacheState.FULL:
                _LOGGER.debug(
                    "Reolink %s has no room to cache %s, using HTTP playback",
                    host.api.nvr_name,
                    filename,
                )
                return None
            if state is _CacheState.DOWNLOAD and not await self._async_cache_vod(
                host, channel, filename, path, info
            ):
                return None

        return web.FileResponse(path, headers={"Content-Type": "video/mp4"})

    @callback
    def _async_vod_serving(self) -> set[Path]:
        """Return the cached paths that may still be streaming to a client."""
        cutoff = time.monotonic() - VOD_CACHE_GRACE
        self._vod_serving = {
            item: seen for item, seen in self._vod_serving.items() if seen > cutoff
        }
        return set(self._vod_serving)

    async def _async_cache_vod(
        self,
        host: ReolinkHost,
        channel: int,
        filename: str,
        path: Path,
        info: dict[str, Any],
    ) -> bool:
        """Download a recording into the cache, False when that did not work."""
        try:
            handle, part = await self.hass.async_add_executor_job(
                _open_part, path.parent
            )
        except OSError as err:
            _LOGGER.warning("Reolink cannot write to the recording cache: %s", err)
            return False

        buffer: list[bytes] = []
        buffered = 0
        try:
            stream = host.api.baichuan.download_vod(channel, filename, info=info)
            async with aclosing(stream) as chunks:
                async for chunk in chunks:
                    buffer.append(chunk)
                    buffered += len(chunk)
                    if buffered >= VOD_WRITE_BUFFER:
                        await self.hass.async_add_executor_job(
                            handle.write, b"".join(buffer)
                        )
                        buffer.clear()
                        buffered = 0
            if buffer:
                await self.hass.async_add_executor_job(handle.write, b"".join(buffer))
        except (ReolinkError, OSError) as err:
            _LOGGER.warning(
                "Reolink %s failed to download %s over Baichuan,"
                " using HTTP playback: %s",
                host.api.nvr_name,
                filename,
                err,
            )
            await self.hass.async_add_executor_job(_discard_part, handle, part)
            return False
        except BaseException:  # the request task is cancelled when a client leaves
            # not awaited, since awaiting again during cancellation would not return
            self.hass.async_add_executor_job(_discard_part, handle, part)
            raise

        return await self.hass.async_add_executor_job(_finish_part, handle, part, path)
