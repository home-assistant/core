"""Cloudflare-Tunnel HLS-Buffering Workaround (HA stream view monkey-patch).

cloudflared buffers HTTP responses by default. Per its source — `shouldFlush()`
in `connection/connection.go` — it only switches to streaming mode when one of:

    (A) no Content-Length header
    (B) Transfer-Encoding contains "chunked"
    (C) Content-Type starts with `text/event-stream` / `application/grpc`
        / `application/x-ndjson`

HA's HLS endpoints (`/api/hls/<token>/*.m3u8` and `*.m4s` segments) return
`application/vnd.apple.mpegurl` / `video/mp4` with `Content-Length` set, so
cloudflared collects each response fully at the edge before forwarding. On
cellular (high RTT) the iOS Companion App's WKWebView times out before the
buffer flushes — visible in the cloudflared add-on log as
`Incoming request ended abruptly: context canceled`. Mobile Safari is more
tolerant on the same network, which is why the same camera works in Safari
on 5G but hangs in the App. WLAN works in both because no buffering boundary
applies on the LAN-direct path.

Two-pronged fix, one per response shape:

1. **Manifests** (`*.m3u8` from `HlsMasterPlaylistView`, `HlsPlaylistView`):
   Rewrite `Content-Type` to `text/event-stream; x-actual=...` — cloudflared
   `HasPrefix`-matches Branch (C) → streams. Players dispatch HLS playlists
   by URL extension and parse them as text, so a bogus Content-Type is fine.

2. **Binary segments** (`init.mp4`, `*.m4s` from `HlsInitView`, `HlsPartView`,
   `HlsSegmentView`): The Content-Type lie does NOT work here — iOS native
   AVFoundation parses these as MP4 and rejects them when the Content-Type
   doesn't match the container. AVPlayer paints the init frame, then the
   segment GET stalls inside cloudflared's buffer for ~10 s before the
   player times out — last decoded frame stays on screen ("Standbild"
   symptom). Instead we re-emit the response as `web.StreamResponse` with
   `Transfer-Encoding: chunked` and no `Content-Length` — that triggers
   cloudflared's Branch (B) without lying about the body type. AVFoundation
   handles HTTP chunked encoding natively (it's HTTP/1.1 standard).

Why view monkey-patch instead of aiohttp middleware / on_response_prepare:
both `app.middlewares` and `app.on_response_prepare` are frozen by HA after
HTTP setup completes — appending after that point either raises
"Cannot modify frozen list" (middlewares) or silently fails. Patching the
view classes works at any time because aiohttp resolves `class_handler.handle`
via getattr at request dispatch time, so a class-level monkey-patch applied
AFTER routes are registered still wins on the next request.

Sources:
- cloudflared shouldFlush(): https://github.com/cloudflare/cloudflared/blob/master/connection/connection.go
- cloudflared#199 (SSE buffered, open since 2022): https://github.com/cloudflare/cloudflared/issues/199
- cloudflared#1095 (Tunnel buffers HTTP responses): https://github.com/cloudflare/cloudflared/issues/1095
- HA stream component HlsSegmentView: https://github.com/home-assistant/core/blob/dev/homeassistant/components/stream/hls.py
- knowledge-base/cloudflared-tunnel-hls-buffering.md (full diagnosis)
"""

from functools import wraps
import logging
import time
from typing import Any, cast

from aiohttp import web

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_FLUSH_PREFIX = "text/event-stream; x-actual="

# ── Live HLS-consumer tracking ────────────────────────────────────────────────
# Every wrapped playlist/segment request stamps the stream's access token here,
# giving the idle-session reaper a REAL "is anyone fetching HLS right now" signal.
# This is needed because HA's `Stream.available` stays True for the whole session
# once HLS was ever used (it means "can serve", not "is serving") — so it cannot
# tell a watched stream from an abandoned one. Keyed by the Stream access_token
# embedded in the HLS URL (/api/hls/<token>/...). See __init__.py
# _has_active_consumer.
_HLS_ACCESS: dict[str, float] = {}
# Cap raised from 64 → 256 (B05-5).  64 was enough for typical deployments,
# but tokens rotate on every HLS session renewal.  With >64 cameras — or after
# many rapid session restarts — the oldest token could be evicted while HLS was
# still actively serving a segment.  hls_access_age() would then return None
# ("never seen"), and the idle-session reaper would misinterpret the missing
# entry as "idle" and tear the stream down mid-delivery.  256 makes overflow
# effectively impossible in any realistic installation (<20 cameras per HA box).
_HLS_ACCESS_MAX = 256
# Re-stamp threshold: if the oldest token was accessed within this many seconds
# it is still active — skip evicting it and evict the second-oldest instead.
# Prevents a slow-segment delivery from being misclassified as idle when the
# dict hits capacity.
_HLS_ACTIVE_WINDOW = 30.0


def _note_hls_access(request: web.Request | None) -> None:
    """Stamp `now` against the stream token in an HLS request path."""
    try:
        parts = request.path.split("/")  # type: ignore[union-attr]
        token = parts[parts.index("hls") + 1]
    except AttributeError, ValueError, IndexError:
        return
    if not token:
        return
    now = time.monotonic()
    _HLS_ACCESS[token] = now
    if len(_HLS_ACCESS) > _HLS_ACCESS_MAX:
        # Evict the oldest token, but skip it if it was recently accessed
        # (i.e. an active stream is still in flight).  In that case promote
        # to the second-oldest so a slow segment fetch is not silently killed.
        sorted_tokens = sorted(_HLS_ACCESS, key=_HLS_ACCESS.__getitem__)
        evict = sorted_tokens[0]
        if now - _HLS_ACCESS[evict] < _HLS_ACTIVE_WINDOW and len(sorted_tokens) > 1:
            evict = sorted_tokens[1]
        _HLS_ACCESS.pop(evict, None)


def hls_access_age(token: str) -> float | None:
    """Seconds since the last HLS request for `token`, or None if never seen."""
    last = _HLS_ACCESS.get(token)
    return None if last is None else time.monotonic() - last


_PLAYLIST_VIEW_CLASSES = (
    "HlsMasterPlaylistView",
    "HlsPlaylistView",
)

_SEGMENT_VIEW_CLASSES = (
    "HlsInitView",
    "HlsPartView",
    "HlsSegmentView",
)


def _wrap_playlist_response(response: web.Response | None) -> web.Response | None:
    """Manifest path — rewrite Content-Type to bypass cloudflared buffer."""
    if response is None or not hasattr(response, "headers"):
        return response
    original = response.headers.get("Content-Type", "")
    if not original.startswith("text/event-stream"):
        response.headers["Content-Type"] = f"{_FLUSH_PREFIX}{original}"
    return response


async def _emit_segment_chunked(
    request: web.Request, response: web.Response
) -> web.StreamResponse | web.Response:
    """Binary-segment path — re-emit body via chunked StreamResponse.

    aiohttp's `web.Response` always sets Content-Length when the body is
    bytes. We need Transfer-Encoding: chunked (no Content-Length) to trigger
    cloudflared's Branch (B). Solution: drop Content-Length, prepare a
    StreamResponse, write the body in one chunk, end. aiohttp emits the
    chunked framing automatically.
    """
    body = response.body
    if not body:
        return response

    new_resp = web.StreamResponse(
        status=response.status,
        reason=response.reason,
    )
    for name, value in response.headers.items():
        if name.lower() in ("content-length", "transfer-encoding"):
            continue
        new_resp.headers[name] = value
    # No Content-Length → aiohttp uses chunked transfer encoding.
    await new_resp.prepare(request)
    # response.body is typed bytes | bytearray | Payload | None by aiohttp,
    # but this handler only ever sees in-memory bytes bodies (never a
    # Payload, which aiohttp only uses for multipart/file-backed responses
    # this integration doesn't construct) -- matches write()'s own narrower
    # accepted type.
    await new_resp.write(cast("bytes | bytearray", body))
    await new_resp.write_eof()
    return new_resp


_PATCHED = False


def _make_playlist_wrapper(orig_handle: Any) -> Any:
    @wraps(orig_handle)
    async def _wrapped(self: Any, *args: Any, **kwargs: Any) -> web.Response | None:
        if args:
            _note_hls_access(args[0])  # args[0] is the aiohttp request
        response = await orig_handle(self, *args, **kwargs)
        return _wrap_playlist_response(response)

    _wrapped._cf_wrapped = True  # type: ignore[attr-defined]
    return _wrapped


def _make_segment_wrapper(orig_handle: Any) -> Any:
    @wraps(orig_handle)
    async def _wrapped(
        self: Any, request: web.Request, *args: Any, **kwargs: Any
    ) -> web.StreamResponse | web.Response | None:
        _note_hls_access(request)
        response = await orig_handle(self, request, *args, **kwargs)
        if response is None or not isinstance(response, web.Response):
            return response
        try:
            return await _emit_segment_chunked(request, response)
        except Exception as exc:  # noqa: BLE001 — this is a best-effort
            # workaround for a Cloudflare-tunnel buffering quirk; any
            # failure re-emitting the response as chunked must fall back to
            # serving the original (unpatched) response rather than break
            # the actual HLS segment delivery.
            _LOGGER.debug("CF unbuffer segment chunked emit failed: %s", exc)
            return response

    _wrapped._cf_wrapped = True  # type: ignore[attr-defined]
    return _wrapped


def register(hass: HomeAssistant) -> None:
    """Patch the HLS segment view to unbuffer chunked responses, once."""
    global _PATCHED  # noqa: PLW0603 -- process-lifetime idempotent-patch guard
    if _PATCHED:
        return
    try:
        from homeassistant.components.stream import hls as _hls

        patched_playlist = []
        for cls_name in _PLAYLIST_VIEW_CLASSES:
            cls = getattr(_hls, cls_name, None)
            if cls is None:
                continue
            orig_handle = getattr(cls, "handle", None)
            if orig_handle is None or getattr(orig_handle, "_cf_wrapped", False):
                continue
            cls.handle = _make_playlist_wrapper(orig_handle)
            patched_playlist.append(cls_name)

        patched_segment = []
        for cls_name in _SEGMENT_VIEW_CLASSES:
            cls = getattr(_hls, cls_name, None)
            if cls is None:
                continue
            orig_handle = getattr(cls, "handle", None)
            if orig_handle is None or getattr(orig_handle, "_cf_wrapped", False):
                continue
            cls.handle = _make_segment_wrapper(orig_handle)
            patched_segment.append(cls_name)

        _PATCHED = True
        _LOGGER.info(
            "Bosch CF-tunnel HLS unbuffer patch applied — "
            "playlists [%s] get text/event-stream Content-Type, "
            "segments [%s] re-emit as chunked StreamResponse "
            "(both bypass cloudflared HTTP buffer)",
            ", ".join(patched_playlist) if patched_playlist else "none",
            ", ".join(patched_segment) if patched_segment else "none",
        )
    except Exception as exc:  # noqa: BLE001 — this optional monkey-patch
        # (import + getattr/setattr on HA's stream views) must never prevent
        # integration setup; any failure here just means the CF-tunnel
        # workaround stays inactive.
        _LOGGER.warning("CF unbuffer patch failed: %s", exc)
