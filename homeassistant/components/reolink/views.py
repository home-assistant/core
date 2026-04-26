"""Reolink Integration views."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Mapping
from contextlib import suppress
import datetime as dt
from http import HTTPStatus
import logging
import re
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientResponse,
    ClientTimeout,
    web,
)
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import SSLCipherList

from .util import get_host

_LOGGER = logging.getLogger(__name__)

_RANGE_HEADER_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")
_CONTENT_RANGE_TOTAL_PATTERN = re.compile(r"^bytes\s+\d+-\d+/(\d+|\*)$")
_FILENAME_DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_HOP_BY_HOP_RESPONSE_HEADERS = {
    "Connection",
    "Keep-Alive",
    "Proxy-Authenticate",
    "Proxy-Authorization",
    "Trailer",
    "Transfer-Encoding",
    "Upgrade",
}


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
    url = "/api/reolink/video/{config_entry_id}/{channel}/{stream_res}/{vod_type}/{filename}.mp4"
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
        self._size_cache: dict[str, int] = {}

    @staticmethod
    def _is_webkit_client(request: web.Request) -> bool:
        """Return True if request appears to come from Safari/WebKit."""
        user_agent = request.headers.get("User-Agent")
        if user_agent is None:
            return False
        return "AppleWebKit" in user_agent and "Chrome" not in user_agent

    @staticmethod
    def _parse_range_header(
        range_header: str, total_length: int
    ) -> tuple[int, int] | None:
        """Parse a single bytes range header.

        Returns start and end (inclusive) when valid, otherwise None.
        """
        match = _RANGE_HEADER_PATTERN.match(range_header.strip())
        if not match:
            return None

        start_str, end_str = match.groups()
        if not start_str and not end_str:
            return None

        if not start_str:
            suffix_length = int(end_str)
            if suffix_length <= 0:
                return None
            start = max(total_length - suffix_length, 0)
            end = total_length - 1
            return start, end

        start = int(start_str)
        end = int(end_str) if end_str else total_length - 1

        if start < 0 or end < start or start >= total_length:
            return None

        return start, min(end, total_length - 1)

    @staticmethod
    def _extract_total_length_from_headers(
        headers: Mapping[str, str],
    ) -> int | None:
        """Extract a total content length from upstream headers when available."""
        content_range = headers.get("Content-Range")
        if content_range is not None:
            match = _CONTENT_RANGE_TOTAL_PATTERN.match(content_range.strip())
            if match:
                total = match.group(1)
                if total != "*":
                    return int(total)

        content_length = headers.get("Content-Length")
        if content_length and content_length.isdigit():
            return int(content_length)

        return None

    async def _async_resolve_total_length(
        self,
        host: Any,
        channel: int,
        stream_res: str,
        filename_decoded: str,
        reolink_url: str,
        reolink_response: ClientResponse,
    ) -> int | None:
        """Resolve and cache total byte length for deterministic range responses."""
        if (cached := self._size_cache.get(reolink_url)) is not None:
            return cached

        if (
            length := self._extract_total_length_from_headers(reolink_response.headers)
        ) is not None:
            self._size_cache[reolink_url] = length
            return length

        try:
            probe_response = await self.session.get(
                reolink_url,
                headers={"Range": "bytes=0-1", "Accept-Encoding": "identity"},
                timeout=ClientTimeout(
                    connect=15, sock_connect=15, sock_read=5, total=None
                ),
            )
        except ClientError:
            return None

        try:
            if (
                length := self._extract_total_length_from_headers(
                    probe_response.headers
                )
            ) is not None:
                self._size_cache[reolink_url] = length
                return length
        finally:
            probe_response.release()

        if (
            length := await self._async_lookup_total_length_from_index(
                host, channel, stream_res, filename_decoded
            )
        ) is not None:
            self._size_cache[reolink_url] = length
            return length

        return None

    async def _async_lookup_total_length_from_index(
        self,
        host: Any,
        channel: int,
        stream_res: str,
        filename_decoded: str,
    ) -> int | None:
        """Fallback: resolve clip size from Reolink VOD index."""
        if (match := _FILENAME_DATE_PATTERN.search(filename_decoded)) is None:
            return None

        year, month, day = map(int, match.groups())
        start = dt.datetime(year, month, day, 0, 0, 0)
        end = dt.datetime(year, month, day, 23, 59, 59)
        basename = filename_decoded.rsplit("/", 1)[-1]

        try:
            _statuses, vod_files = await host.api.request_vod_files(
                channel, start, end, stream=stream_res
            )
        except ReolinkError:
            return None

        for vod_file in vod_files:
            file_name = getattr(vod_file, "file_name", None)
            if not isinstance(file_name, str) or (
                file_name != basename and file_name not in filename_decoded
            ):
                continue
            for attr in ("size", "file_size", "length"):
                value = getattr(vod_file, attr, None)
                if isinstance(value, int) and value > 0:
                    return value

        return None

    def _plan_range_handling(
        self,
        request: web.Request,
        reolink_response: ClientResponse,
        total_length: int | None,
    ) -> tuple[tuple[int, int] | None, str | int, web.Response | None]:
        """Plan range handling for the current request/response pair."""
        range_header = request.headers.get("Range")
        if (
            range_header is None
            or reolink_response.status == HTTPStatus.PARTIAL_CONTENT
        ):
            return None, reolink_response.content_length or "*", None

        content_range_total: str | int = total_length or "*"
        if total_length is not None:
            force_range = self._parse_range_header(range_header, total_length)
            if force_range is None:
                return (
                    None,
                    content_range_total,
                    web.Response(
                        status=HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
                        headers={
                            "Accept-Ranges": "bytes",
                            "Content-Range": f"bytes */{total_length}",
                        },
                    ),
                )
            return force_range, content_range_total, None

        # WebKit/Safari expects Partial Content for its initial probe,
        # even when the upstream does not expose total length.
        if self._is_webkit_client(request) and range_header == "bytes=0-1":
            return (0, 1), content_range_total, None

        # If total size is unknown we cannot safely synthesize strict ranges,
        # so fall back to passthrough semantics.
        return None, content_range_total, None

    async def _async_open_reolink_stream(
        self,
        request: web.Request,
        host: Any,
        reolink_url: str,
        headers: dict[str, str],
        config_entry_id: str,
        channel: str,
        stream_res: str,
        vod_type: str,
        filename: str,
        retry: int,
    ) -> ClientResponse | web.StreamResponse:
        """Open upstream stream, handling retry behavior on client errors."""
        try:
            return await self.session.get(
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
                request,
                config_entry_id,
                channel,
                stream_res,
                vod_type,
                filename,
                retry,
            )

    async def _async_handle_unsupported_content_type(
        self,
        request: web.Request,
        reolink_response: ClientResponse,
        vod_type: str,
        config_entry_id: str,
        channel: str,
        stream_res: str,
        filename: str,
        retry: int,
    ) -> web.StreamResponse:
        """Handle unsupported content types."""
        err_str = (
            "Reolink playback expected video/mp4 but got "
            f"{reolink_response.content_type}"
        )
        if (
            reolink_response.content_type == "video/x-flv"
            and vod_type == VodRequestType.PLAYBACK.value
        ):
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

    @staticmethod
    def _normalize_content_type(headers: dict[str, str], content_type: str) -> None:
        """Ensure a valid content type header exists and fix Reolink typo."""
        if "Content-Type" not in headers:
            headers["Content-Type"] = content_type
        if headers["Content-Type"] == "apolication/octet-stream":
            headers["Content-Type"] = "application/octet-stream"

    async def _async_stream_body(
        self,
        response: web.StreamResponse,
        reolink_response: ClientResponse,
        host: Any,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> None:
        """Copy upstream response body, optionally slicing to a byte range."""
        current_pos = 0
        remaining = (
            range_end - range_start + 1
            if range_start is not None and range_end is not None
            else None
        )

        try:
            async for chunk in reolink_response.content.iter_chunked(65536):
                if range_start is not None and remaining is not None:
                    chunk_len = len(chunk)
                    if current_pos + chunk_len <= range_start:
                        current_pos += chunk_len
                        continue

                    if current_pos < range_start:
                        chunk = chunk[range_start - current_pos :]
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]

                    current_pos += chunk_len
                    remaining -= len(chunk)
                    if not chunk:
                        continue
                    await response.write(chunk)
                    if remaining <= 0:
                        break
                    continue

                await response.write(chunk)
        except TimeoutError, ConnectionResetError, ClientConnectionError:
            _LOGGER.debug(
                "Timeout while reading Reolink playback from %s, writing EOF",
                host.api.nvr_name,
            )
        finally:
            reolink_response.release()

        with suppress(ConnectionResetError, ClientConnectionError):
            await response.write_eof()

    async def _async_stream_passthrough(
        self,
        request: web.Request,
        host: Any,
        reolink_response: ClientResponse,
    ) -> web.StreamResponse:
        """Stream the upstream response without any range synthesis."""
        response_headers = dict(reolink_response.headers)
        response_headers.pop("Content-Disposition", None)
        response_headers.pop("content-disposition", None)
        self._normalize_content_type(response_headers, reolink_response.content_type)

        response = web.StreamResponse(
            status=reolink_response.status,
            reason=reolink_response.reason,
            headers=response_headers,
        )
        await response.prepare(request)
        await self._async_stream_body(response, reolink_response, host)
        return response

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
        if self._vod_type is not None:
            vod_type = self._vod_type
        try:
            host = get_host(self.hass, config_entry_id)
        except Unresolvable:
            err_str = f"Reolink playback proxy could not find config entry id: {config_entry_id}"
            _LOGGER.warning(err_str)
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

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

        reolink_response_or_result = await self._async_open_reolink_stream(
            request,
            host,
            reolink_url,
            headers,
            config_entry_id,
            channel,
            stream_res,
            vod_type,
            filename,
            retry,
        )
        if isinstance(reolink_response_or_result, web.StreamResponse):
            return reolink_response_or_result
        reolink_response = reolink_response_or_result

        if reolink_response.content_type not in {
            "video/mp4",
            "application/octet-stream",
            "apolication/octet-stream",
        }:
            return await self._async_handle_unsupported_content_type(
                request,
                reolink_response,
                vod_type,
                config_entry_id,
                channel,
                stream_res,
                filename,
                retry,
            )

        if not self._is_webkit_client(request):
            return await self._async_stream_passthrough(request, host, reolink_response)

        total_length = await self._async_resolve_total_length(
            host,
            ch,
            stream_res,
            filename_decoded,
            reolink_url,
            reolink_response,
        )
        force_range, content_range_total, error_response = self._plan_range_handling(
            request, reolink_response, total_length
        )
        if error_response is not None:
            return error_response

        response_headers = dict(reolink_response.headers)
        for header in _HOP_BY_HOP_RESPONSE_HEADERS:
            response_headers.pop(header, None)
            response_headers.pop(header.lower(), None)
        response_headers.pop("Content-Disposition", None)
        response_headers.pop("content-disposition", None)
        response_headers["Accept-Ranges"] = "bytes"

        status = reolink_response.status
        reason = reolink_response.reason
        range_start: int | None = None
        range_end: int | None = None
        if force_range is not None:
            range_start, range_end = force_range
            status = HTTPStatus.PARTIAL_CONTENT
            reason = HTTPStatus.PARTIAL_CONTENT.phrase
            response_headers["Content-Range"] = (
                f"bytes {range_start}-{range_end}/{content_range_total}"
            )
            response_headers["Content-Length"] = str(range_end - range_start + 1)
        elif reolink_response.content_length is not None:
            response_headers["Content-Length"] = str(reolink_response.content_length)

        _LOGGER.debug(
            "Response Playback Proxy Status %s:%s, Headers: %s",
            status,
            reason,
            response_headers,
        )
        self._normalize_content_type(response_headers, reolink_response.content_type)

        response = web.StreamResponse(
            status=status,
            reason=reason,
            headers=response_headers,
        )

        await response.prepare(request)

        await self._async_stream_body(
            response,
            reolink_response,
            host,
            range_start=range_start,
            range_end=range_end,
        )
        return response
