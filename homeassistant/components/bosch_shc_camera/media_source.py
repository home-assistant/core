"""Media source for Bosch Smart Home Camera event recordings.

Exposes downloaded events under HA's "Media" browser. Two backends:

* **Local** (``options['download_path']``, FCM-triggered saves)
  Files on HA's filesystem. Layout: ``{download_path}/{camera}/{stem}.{ext}``.

* **SMB / NAS** (``options['enable_smb_upload'] + smb_*``)
  Files on a remote SMB share. Layout follows the configured patterns; the
  default is ``{base_path}/{camera}/{YYYY}/{MM}/{DD}/{camera}_{date}_{time}_{type}_{id}.{ext}``
  with one folder per camera at the top level.

Both backends are read-only and are served through ``/api/bosch_shc_camera/event/…``,
an authenticated ``HomeAssistantView`` with HTTP Range support so video clips can
seek. When only one backend is configured, the source/backend chooser is hidden
so users land directly on the meaningful content.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
import logging
import mimetypes
from pathlib import Path
import re
from typing import Any, override

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import raise_if_invalid_path

from .const import DEFAULT_OPTIONS, DOMAIN
from .smb import smb_available

_LOGGER = logging.getLogger(__name__)

URL_PREFIX = f"/api/{DOMAIN}/event"
VIEW_REGISTERED_KEY = f"{DOMAIN}_media_view_registered"

# Filename pattern: "{Camera}_{YYYY-MM-DD}_{HH-MM-SS}_{TYPE}_{ID}.ext"
_FILE_RE = re.compile(
    r"^(?:(?P<camera>.+?)_)?(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2}-\d{2})_(?P<etype>[A-Z_]+)_[0-9A-F]+\.(?P<ext>jpg|jpeg|mp4)$",
    re.IGNORECASE,
)
_DATE_DIR_RE = re.compile(r"^\d{2}$")  # YY-style two-digit dir name (year/month/day)
_YEAR_RE = re.compile(r"^\d{4}$")
# NVR segment files: "HH-MM.mp4" (5-min wall-aligned segments).
_NVR_SEG_RE = re.compile(r"^(?P<time>\d{2}-\d{2})\.mp4$")
_NVR_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# SMB clip/thumbnail streaming chunk size. Each chunk is one
# `hass.async_add_executor_job` hop (fobj.read is blocking smbclient I/O),
# so a large clip at the old 256 KiB was ~2000 executor hops for a 500 MB
# file. Bumped to 1 MiB: smbprotocol/SMB2 negotiates a max read size per
# connection (commonly up to 1 MiB with a single server-side credit on the
# NAS/Windows servers this integration targets; larger reads either get
# split by smbprotocol into multiple wire requests transparently or need
# multi-credit negotiation this integration doesn't rely on), so this stays
# within one wire-request's worth of data per hop while cutting the hop
# count ~4x. Not raised further (e.g. to 4 MiB): that would risk exceeding
# some servers' negotiated max read size per single request, and the
# per-chunk buffer is held in memory for the duration of one `response.write`
# — 1 MiB is a reasonable ceiling for concurrent range-request streams.
_CHUNK = 1024 * 1024


# ── helpers ──────────────────────────────────────────────────────────────────
def _safe_join(base: Path, relative: str) -> Path | None:
    try:
        raise_if_invalid_path(relative)
    except ValueError:
        return None
    base_abs = base.resolve()
    target = (base_abs / relative).resolve()
    try:
        target.relative_to(base_abs)
    except ValueError:
        return None
    return target


def _is_macos_junk(name: str) -> bool:
    return name.startswith("._") or name == ".DS_Store"


def _parse_filename(name: str) -> dict[str, str] | None:
    m = _FILE_RE.match(name)
    return m.groupdict() if m else None


def _format_event_title(parsed: dict[str, str]) -> str:
    cam = parsed.get("camera") or ""
    suffix = f"  ({cam})" if cam else ""
    return f"{parsed['time'].replace('-', ':')} — {parsed['etype']}{suffix}"


def _entry_title(hass: HomeAssistant, entry_id: str) -> str:
    cfg = hass.config_entries.async_get_entry(entry_id)
    return cfg.title if cfg else entry_id


# ── backends ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Source:
    entry_id: str
    kind: str  # "L" (local) or "S" (smb)
    label: str  # "Lokal" / "NAS …"


class _LocalBackend:
    """Read events from a local directory.

    Two tree modes driven by folder_pattern (same option as NAS uploads):
    - camera_first=True  (default, pattern starts with {camera}):
        camera / year / month / day / events  — matches new save structure
    - camera_first=False (legacy flat, pattern starts with {year}):
        camera / date-from-filename / events  — old single-folder-per-camera
    """

    def __init__(
        self, base: str, folder_pattern: str = "{camera}/{year}/{month}/{day}"
    ) -> None:
        self.base = Path(base)
        self.folder_pattern = folder_pattern.strip()

    @property
    def camera_first(self) -> bool:
        return self.folder_pattern.lstrip("/").startswith("{camera}")

    def list_cameras(self) -> list[str]:
        if not self.base.is_dir():
            return []
        return sorted(
            (
                p.name
                for p in self.base.iterdir()
                if p.is_dir()
                and not _is_macos_junk(p.name)
                and not p.name.startswith("_")
            ),
            key=str.casefold,
        )

    # ── year-first methods (year/month/day at root, no camera subdir) ───────────
    def list_year_first_months(self, year: str) -> list[str]:
        d = _safe_join(self.base, year)
        if d is None or not d.is_dir():
            return []
        return sorted(
            [p.name for p in d.iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name)],
            reverse=True,
        )

    def list_year_first_days(self, year: str, month: str) -> list[str]:
        d = _safe_join(self.base, year)
        if d is None:
            return []
        d = _safe_join(d, month)
        if d is None or not d.is_dir():
            return []
        return sorted(
            [p.name for p in d.iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name)],
            reverse=True,
        )

    def list_year_first_events(
        self, year: str, month: str, day: str
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        d = _safe_join(self.base, year)
        if d is None:
            return []
        d2 = _safe_join(d, month)
        if d2 is None:
            return []
        d3 = _safe_join(d2, day)
        if d3 is None or not d3.is_dir():
            return []
        return self._collect_events(d3)

    # ── camera-first methods (year/month/day subfolders) ──────────────────────
    def list_years(self, camera: str) -> list[str]:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None or not cam_dir.is_dir():
            return []
        return sorted(
            (
                p.name
                for p in cam_dir.iterdir()
                if p.is_dir() and _YEAR_RE.match(p.name)
            ),
            reverse=True,
        )

    def list_months(self, camera: str, year: str) -> list[str]:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None:
            return []
        year_dir = _safe_join(cam_dir, year)
        if year_dir is None or not year_dir.is_dir():
            return []
        return sorted(
            (
                p.name
                for p in year_dir.iterdir()
                if p.is_dir() and _DATE_DIR_RE.match(p.name)
            ),
            reverse=True,
        )

    def list_days(self, camera: str, year: str, month: str) -> list[str]:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None:
            return []
        month_dir = _safe_join(cam_dir, year)
        if month_dir is None:
            return []
        month_dir = _safe_join(month_dir, month)
        if month_dir is None or not month_dir.is_dir():
            return []
        return sorted(
            (
                p.name
                for p in month_dir.iterdir()
                if p.is_dir() and _DATE_DIR_RE.match(p.name)
            ),
            reverse=True,
        )

    def list_events_dated(
        self, camera: str, year: str, month: str, day: str
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        """Events from camera/year/month/day/ subfolder."""
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None:
            return []
        # Validate the date components before joining — they come from the media
        # identifier (split on "/") and were NOT sanitised, so a crafted value
        # like ".." would escape the camera directory (path traversal). The
        # regexes only admit purely-numeric two/four-digit names.
        if not (
            _YEAR_RE.match(year)
            and _DATE_DIR_RE.match(month)
            and _DATE_DIR_RE.match(day)
        ):
            return []
        day_dir = cam_dir / year / month / day
        if not day_dir.is_dir():
            return []
        return self._collect_events(day_dir)

    # ── legacy flat methods (files directly in camera/ folder) ───────────────
    def list_dates(self, camera: str) -> list[str]:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None or not cam_dir.is_dir():
            return []
        dates: set[str] = set()
        for f in cam_dir.iterdir():
            if not f.is_file() or _is_macos_junk(f.name):
                continue
            parsed = _parse_filename(f.name)
            if parsed:
                dates.add(parsed["date"])
        return sorted(dates, reverse=True)

    def list_events(
        self, camera: str, date: str
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        """Events from flat camera/ folder, filtered by date."""
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None or not cam_dir.is_dir():
            return []
        groups: dict[str, dict[str, Any]] = {}
        for f in cam_dir.iterdir():
            if not f.is_file() or _is_macos_junk(f.name):
                continue
            parsed = _parse_filename(f.name)
            if not parsed or parsed["date"] != date:
                continue
            stem = f.stem
            ext = f.suffix.lower().lstrip(".")
            slot = groups.setdefault(stem, {"parsed": parsed, "files": {}})
            slot["files"][ext] = f.name
        return self._groups_to_events(groups)

    # ── shared helpers ────────────────────────────────────────────────────────
    def _collect_events(
        self, directory: Path
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        groups: dict[str, dict[str, Any]] = {}
        for f in directory.iterdir():
            if not f.is_file() or _is_macos_junk(f.name):
                continue
            parsed = _parse_filename(f.name)
            if not parsed:
                continue
            stem = f.stem
            ext = f.suffix.lower().lstrip(".")
            slot = groups.setdefault(stem, {"parsed": parsed, "files": {}})
            slot["files"][ext] = f.name
        return self._groups_to_events(groups)

    def _groups_to_events(
        self, groups: dict[str, Any]
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        out: list[tuple[str, str | None, dict[str, str]]] = []
        for stem in sorted(groups, reverse=True):
            files = groups[stem]["files"]
            video = files.get("mp4")
            image = files.get("jpg") or files.get("jpeg")
            preferred = video or image
            if preferred:
                out.append((preferred, image, groups[stem]["parsed"]))
        return out

    def resolve(self, *segments: str) -> Path | None:
        cur = self.base
        for s in segments:
            nxt = _safe_join(cur, s)
            if nxt is None:
                return None
            cur = nxt
        return cur if cur.is_file() else None


class _SmbBackend:
    """Read events from an SMB share via smbclient (requirements pulls smbprotocol).

    Each public read uses its own ``connection_cache`` dict so smbprotocol creates
    a fresh ``Connection`` per call. Sharing one session across concurrent HTTP
    range-requests exhausts the per-Connection SMB2 credit pool (~64 credits) and
    raises ``Request requires 1 credits but only 0 credits are available``.
    Per-call cache = per-call credit window. See knowledge-base/smb-credit-starvation.md.
    """

    def __init__(self, hass: HomeAssistant, opts: dict[str, Any]) -> None:
        self.hass = hass
        self.server = (opts.get("smb_server") or "").strip()
        self.share = (opts.get("smb_share") or "").strip()
        self.username = (opts.get("smb_username") or "").strip()
        self.password = opts.get("smb_password") or ""
        self.protocol = (opts.get("upload_protocol") or "smb").upper()
        base = (opts.get("smb_base_path") or "").strip().strip("/")
        self.base_parts: tuple[str, ...] = tuple(p for p in base.split("/") if p)
        self.folder_pattern: str = (
            opts.get("folder_pattern") or "{camera}/{year}/{month}/{day}"
        ).strip()

    @property
    def camera_first(self) -> bool:
        """True when folder_pattern starts with {camera} → Camera/Year/Month/Day tree."""
        return self.folder_pattern.lstrip("/").startswith("{camera}")

    @property
    def configured(self) -> bool:
        return bool(self.server and self.share)

    @property
    def label(self) -> str:
        base = "\\".join(self.base_parts)
        path = f"\\{self.share}\\{base}" if base else f"\\{self.share}"
        return f"{self.protocol}:\\\\{self.server}{path}"

    def _new_session_cache(self) -> dict[str, Any]:
        """Build a fresh connection_cache dict + register a session into it.

        Returning a new dict per call forces smbclient to instantiate a new
        ``Connection`` object (= new TCP socket + new SMB2 sequence_window),
        so concurrent callers don't contend on one credit pool.
        """
        cache: dict[str, Any] = {}
        # smbclient is an optional third-party dependency (see smb.py's
        # smb_available() docstring) — deferred so its absence doesn't
        # break importing this module, only this SMB browse/download path
        # (callers are expected to have checked smb_available() first).
        from smbclient import register_session  # noqa: PLC0415

        register_session(
            self.server,
            username=self.username,
            password=self.password,
            connection_cache=cache,
        )
        return cache

    def _close_session_cache(self, cache: dict[str, Any]) -> None:
        """Best-effort tear-down so the Connection's TCP socket can close.

        Without this, sessions linger in ``cache`` (held by the fobj's connection
        ref) and the NAS sees an ever-growing pile of half-idle sessions.
        """
        try:
            # smbclient is an optional third-party dependency (see smb.py's
            # smb_available() docstring) — deferred so its absence doesn't
            # break importing this module, only this SMB browse/download path
            # (callers are expected to have checked smb_available() first).
            from smbclient import delete_session  # noqa: PLC0415

            delete_session(self.server, connection_cache=cache)
        except (
            Exception
        ):  # pragma: no cover — best-effort SMB session cleanup, failure non-actionable
            pass

    def _path(self, *segments: str) -> str:
        """Build the UNC path, rejecting any traversal attempt in *segments*.

        Regression (bug-hunt 2026-07-03): `camera` (and the other path
        segments from callers like list_years/list_months/list_days/
        open_file/open_flat_file) reached this string-join with ZERO
        validation — unlike `filename`, which every caller already
        re-validates against exactly this pattern before calling _path().
        Camera titles come from the Bosch cloud account (in principle
        attacker-influenceable) and `media_content_id` segments are
        reachable via any media_source.resolve_media call, not just this
        integration's own browse UI, so a crafted segment containing
        "..\\" could escape `{share}\\{base}\\{camera}\\...` and read/list
        outside the intended NAS tree. Same reject pattern as filename
        validation elsewhere in this file, applied at the single choke
        point every segment passes through.
        """
        for seg in segments:
            if not seg:
                continue
            if "/" in seg or "\\" in seg or seg in (".", ".."):
                raise FileNotFoundError(seg)
        all_parts = (self.share, *self.base_parts, *(s for s in segments if s))
        return "\\\\" + self.server + "\\" + "\\".join(all_parts)

    def _scandir_filtered(
        self,
        *segments: str,
        want_dirs: bool,
        session: dict[str, Any] | None = None,
    ) -> Generator[str]:
        """List one directory's entries.

        `session` lets a caller that is about to make several of these calls
        in a row (one `_browse()` step can descend through 1-2 listing calls
        for a single tree node, e.g. `_browse_smb`'s year-first vs. flat-date
        probe) supply an already-open connection_cache to reuse instead of
        paying a fresh TCP+SMB2-session handshake per call. This is safe
        WITHIN one sequential browse step — the credit-starvation risk this
        class's docstring describes is about *concurrent* callers (parallel
        HTTP range-requests via open_file/open_flat_file, which still always
        get a fresh per-call cache, unchanged) contending on one connection's
        SMB2 credit pool, not about reusing a cache across a handful of
        sequential scandir calls issued one after another by the same
        browse() invocation. When `session` is omitted (the default), the
        pre-existing per-call behavior is unchanged: a fresh cache is opened
        and closed here.
        """
        # smbclient is an optional third-party dependency (see smb.py's
        # smb_available() docstring) — deferred so its absence doesn't
        # break importing this module, only this SMB browse/download path
        # (callers are expected to have checked smb_available() first).
        from smbclient import scandir  # noqa: PLC0415

        owns_cache = session is None
        cache = session if session is not None else self._new_session_cache()
        try:
            path = self._path(*segments)
            for e in scandir(path, connection_cache=cache):
                if _is_macos_junk(e.name):
                    continue
                # Skip NVR internal dirs (_staging, _failed, etc.)
                if want_dirs and e.name.startswith("_"):
                    continue
                if (want_dirs and e.is_dir()) or (not want_dirs and e.is_file()):
                    yield e.name
        finally:
            if owns_cache:
                self._close_session_cache(cache)

    # tree (camera-first: camera/year/month/day)
    def list_cameras(self, session: dict[str, Any] | None = None) -> list[str]:
        return sorted(
            (n for n in self._scandir_filtered(want_dirs=True, session=session)),
            key=str.casefold,
        )

    # ── year-first methods (year/month/day at root, no camera subdir) ───────────
    def list_year_first_months(
        self, year: str, session: dict[str, Any] | None = None
    ) -> list[str]:
        return sorted(
            (
                n
                for n in self._scandir_filtered(year, want_dirs=True, session=session)
                if _DATE_DIR_RE.match(n)
            ),
            reverse=True,
        )

    def list_year_first_days(
        self, year: str, month: str, session: dict[str, Any] | None = None
    ) -> list[str]:
        return sorted(
            (
                n
                for n in self._scandir_filtered(
                    year, month, want_dirs=True, session=session
                )
                if _DATE_DIR_RE.match(n)
            ),
            reverse=True,
        )

    def list_year_first_events(
        self,
        year: str,
        month: str,
        day: str,
        session: dict[str, Any] | None = None,
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        groups: dict[str, dict[str, Any]] = {}
        for name in self._scandir_filtered(
            year, month, day, want_dirs=False, session=session
        ):
            parsed = _parse_filename(name)
            if not parsed:
                continue
            stem, _, ext = name.rpartition(".")
            slot = groups.setdefault(stem, {"parsed": parsed, "files": {}})
            slot["files"][ext.lower()] = name
        out: list[tuple[str, str | None, dict[str, str]]] = []
        for stem in sorted(groups, reverse=True):
            files = groups[stem]["files"]
            video = files.get("mp4")
            image = files.get("jpg") or files.get("jpeg")
            preferred = video or image
            if preferred:
                out.append((preferred, image, groups[stem]["parsed"]))
        return out

    def list_years(
        self, camera: str, session: dict[str, Any] | None = None
    ) -> list[str]:
        return sorted(
            (
                n
                for n in self._scandir_filtered(camera, want_dirs=True, session=session)
                if _YEAR_RE.match(n)
            ),
            reverse=True,
        )

    def list_months(
        self, camera: str, year: str, session: dict[str, Any] | None = None
    ) -> list[str]:
        return sorted(
            (
                n
                for n in self._scandir_filtered(
                    camera, year, want_dirs=True, session=session
                )
                if _DATE_DIR_RE.match(n)
            ),
            reverse=True,
        )

    def list_days(
        self,
        camera: str,
        year: str,
        month: str,
        session: dict[str, Any] | None = None,
    ) -> list[str]:
        return sorted(
            (
                n
                for n in self._scandir_filtered(
                    camera, year, month, want_dirs=True, session=session
                )
                if _DATE_DIR_RE.match(n)
            ),
            reverse=True,
        )

    def list_events(
        self,
        camera: str,
        year: str,
        month: str,
        day: str,
        session: dict[str, Any] | None = None,
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        """Return [(preferred_filename, image_filename_or_none, parsed)]."""
        groups: dict[str, dict[str, Any]] = {}
        for name in self._scandir_filtered(
            camera, year, month, day, want_dirs=False, session=session
        ):
            parsed = _parse_filename(name)
            if not parsed:
                continue
            stem, _, ext = name.rpartition(".")
            slot = groups.setdefault(stem, {"parsed": parsed, "files": {}})
            slot["files"][ext.lower()] = name
        out: list[tuple[str, str | None, dict[str, str]]] = []
        for stem in sorted(groups, reverse=True):
            files = groups[stem]["files"]
            video = files.get("mp4")
            image = files.get("jpg") or files.get("jpeg")
            preferred = video or image
            if preferred:
                out.append((preferred, image, groups[stem]["parsed"]))
        return out

    def open_file(
        self, camera: str, year: str, month: str, day: str, filename: str
    ) -> tuple[Any, int]:
        """Return (file-like, size). Caller closes the file-like.

        The returned fobj carries a ``_bosch_close_cache`` callable; the HTTP
        streamer invokes it after fobj.close() so the per-request SMB session
        is torn down.
        """
        # smbclient is an optional third-party dependency (see smb.py's
        # smb_available() docstring) — deferred so its absence doesn't
        # break importing this module, only this SMB browse/download path
        # (callers are expected to have checked smb_available() first).
        from smbclient import open_file, stat as smb_stat  # noqa: PLC0415

        # Re-validate filename to block path traversal
        if (
            "/" in filename
            or "\\" in filename
            or filename in (".", "..")
            or _is_macos_junk(filename)
        ):
            raise FileNotFoundError(filename)
        if not _parse_filename(filename):
            raise FileNotFoundError(filename)
        cache = self._new_session_cache()
        try:
            path = self._path(camera, year, month, day, filename)
            st = smb_stat(path, connection_cache=cache)
            # share_access="r": allow other readers (FRITZ.NAS opens exclusive
            # by default → NtStatus 0xc0000043 on a 2nd parallel range-request).
            fobj = open_file(path, mode="rb", share_access="r", connection_cache=cache)
            fobj._bosch_close_cache = lambda: self._close_session_cache(cache)
            return fobj, st.st_size
        except Exception:
            self._close_session_cache(cache)
            raise

    # ── flat-file methods (files directly in camera/ folder on NAS) ──────────
    def list_flat_dates(
        self, camera: str, session: dict[str, Any] | None = None
    ) -> list[str]:
        """Dates from files directly in camera/ (legacy flat layout)."""
        dates: set[str] = set()
        try:
            for name in self._scandir_filtered(
                camera, want_dirs=False, session=session
            ):
                parsed = _parse_filename(name)
                if parsed:
                    dates.add(parsed["date"])
        except OSError:
            pass
        return sorted(dates, reverse=True)

    def list_flat_events(
        self, camera: str, date: str, session: dict[str, Any] | None = None
    ) -> list[tuple[str, str | None, dict[str, str]]]:
        """Events directly in camera/ folder, filtered by date."""
        groups: dict[str, dict[str, Any]] = {}
        try:
            for name in self._scandir_filtered(
                camera, want_dirs=False, session=session
            ):
                parsed = _parse_filename(name)
                if not parsed or parsed["date"] != date:
                    continue
                stem, _, ext = name.rpartition(".")
                slot = groups.setdefault(stem, {"parsed": parsed, "files": {}})
                slot["files"][ext.lower()] = name
        except OSError:
            pass
        out: list[tuple[str, str | None, dict[str, str]]] = []
        for stem in sorted(groups, reverse=True):
            files = groups[stem]["files"]
            video = files.get("mp4")
            image = files.get("jpg") or files.get("jpeg")
            preferred = video or image
            if preferred:
                out.append((preferred, image, groups[stem]["parsed"]))
        return out

    def open_flat_file(self, camera: str, filename: str) -> tuple[Any, int]:
        """Return (file-like, size) for a file directly in camera/ folder."""
        # smbclient is an optional third-party dependency (see smb.py's
        # smb_available() docstring) — deferred so its absence doesn't
        # break importing this module, only this SMB browse/download path
        # (callers are expected to have checked smb_available() first).
        from smbclient import open_file, stat as smb_stat  # noqa: PLC0415

        if (
            "/" in filename
            or "\\" in filename
            or filename in (".", "..")
            or _is_macos_junk(filename)
        ):
            raise FileNotFoundError(filename)
        if not _parse_filename(filename):
            raise FileNotFoundError(filename)
        cache = self._new_session_cache()
        try:
            path = self._path(camera, filename)
            st = smb_stat(path, connection_cache=cache)
            # share_access="r": allow other readers (see open_file for context).
            fobj = open_file(path, mode="rb", share_access="r", connection_cache=cache)
            fobj._bosch_close_cache = lambda: self._close_session_cache(cache)
            return fobj, st.st_size
        except Exception:
            self._close_session_cache(cache)
            raise


class _NvrBackend:
    """Read continuous-recording segments from the local NVR base path.

    Layout: ``{base}/{Camera}/{YYYY-MM-DD}/HH-MM.mp4`` (Phase 1 MVP).
    """

    def __init__(self, base: str) -> None:
        self.base = Path(base)

    def list_cameras(self) -> list[str]:
        if not self.base.is_dir():
            return []
        return sorted(
            (
                p.name
                for p in self.base.iterdir()
                if p.is_dir()
                and not _is_macos_junk(p.name)
                and not p.name.startswith("_")
            ),
            key=str.casefold,
        )

    def list_dates(self, camera: str) -> list[str]:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None or not cam_dir.is_dir():
            return []
        return sorted(
            (
                d.name
                for d in cam_dir.iterdir()
                if d.is_dir() and _NVR_DATE_DIR_RE.match(d.name)
            ),
            reverse=True,
        )

    def list_segments(self, camera: str, date: str) -> list[tuple[str, str]]:
        """Return [(filename, label_HH:MM)] for one (camera, date)."""
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None:
            return []
        date_dir = _safe_join(cam_dir, date)
        if date_dir is None or not date_dir.is_dir():
            return []
        out: list[tuple[str, str]] = []
        for f in date_dir.iterdir():
            if not f.is_file() or _is_macos_junk(f.name):
                continue
            m = _NVR_SEG_RE.match(f.name)
            if not m:
                continue
            label = m.group("time").replace("-", ":")
            out.append((f.name, label))
        out.sort(reverse=True)
        return out

    def resolve(self, camera: str, date: str, filename: str) -> Path | None:
        cam_dir = _safe_join(self.base, camera)
        if cam_dir is None:
            return None
        date_dir = _safe_join(cam_dir, date)
        if date_dir is None:
            return None
        if not _NVR_DATE_DIR_RE.match(date) or not _NVR_SEG_RE.match(filename):
            return None
        target = _safe_join(date_dir, filename)
        return target if target is not None and target.is_file() else None


# ── source registry ──────────────────────────────────────────────────────────
def _enabled_sources(
    hass: HomeAssistant,
) -> list[tuple[_Source, _LocalBackend | _SmbBackend | _NvrBackend]]:
    out: list[tuple[_Source, _LocalBackend | _SmbBackend | _NvrBackend]] = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coord = getattr(entry, "runtime_data", None)
        if coord is None:
            continue
        entry_id = entry.entry_id
        opts = coord.options

        # Local events — show whenever a download_path is configured (regardless
        # of enable_local_save so already-saved files stay browseable even after
        # the option is toggled off).
        if opts.get("download_path"):
            base = str(
                (opts.get("download_path") or "").strip()
                or DEFAULT_OPTIONS.get("download_path", "")
            )
            fp = (opts.get("folder_pattern") or "{camera}/{year}/{month}/{day}").strip()
            try:
                base_path = Path(base)
                if not base_path.exists():
                    base_path.mkdir(parents=True, exist_ok=True)
                if base_path.is_dir():
                    out.append(
                        (_Source(entry_id, "L", "Lokal"), _LocalBackend(base, fp))
                    )
            except OSError:
                pass

        # NAS — show whenever SMB upload is enabled and credentials are present.
        # Decoupled from upload_protocol: files uploaded via FTP land on the same
        # NAS share and are readable via SMB, so we browse via SMB regardless of
        # how they were uploaded.
        # smb_available() gate: `smbprotocol` is an optional runtime dependency
        # (manifest.json requirement that can fail to install on an unsupported
        # OS/architecture). Without this check, a configured-but-unavailable SMB
        # source would be listed here and then raise an uncaught ImportError
        # deep in _SmbBackend the moment it's actually browsed/opened — this
        # keeps the degradation clean (source just doesn't appear) instead of a
        # crash; __init__.py's _refresh_smb_unavailable_issue surfaces the real
        # cause via a Repairs issue.
        if opts.get("enable_smb_upload") and smb_available():
            smb = _SmbBackend(hass, opts)
            if smb.configured:
                out.append((_Source(entry_id, "S", smb.label), smb))

        # Mini-NVR continuous recording segments.
        if opts.get("enable_nvr"):
            base = (opts.get("nvr_base_path") or "/config/bosch_nvr").strip()
            try:
                base_path = Path(base)
                if base_path.is_dir():
                    out.append((_Source(entry_id, "N", "Aufnahmen"), _NvrBackend(base)))
            except OSError:
                pass
    return out


def _find_source(
    hass: HomeAssistant, entry_id: str, kind: str
) -> tuple[_Source, _LocalBackend | _SmbBackend | _NvrBackend] | None:
    for src, backend in _enabled_sources(hass):
        if src.entry_id == entry_id and src.kind == kind:
            return src, backend
    return None


# ── media source ────────────────────────────────────────────────────────────
async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    if not hass.data.get(VIEW_REGISTERED_KEY):
        hass.http.register_view(BoschCameraMediaView(hass))
        hass.data[VIEW_REGISTERED_KEY] = True
    return BoschCameraMediaSource(hass)


def _node(
    *,
    identifier: str,
    title: str,
    media_class: str = MediaClass.DIRECTORY,
    media_content_type: str = "",
    children: list[BrowseMediaSource] | None = None,
    children_media_class: str = MediaClass.DIRECTORY,
    can_play: bool = False,
    can_expand: bool = True,
    thumbnail: str | None = None,
) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=media_class,
        media_content_type=media_content_type,
        title=title,
        can_play=can_play,
        can_expand=can_expand,
        children=children,
        children_media_class=children_media_class,
        thumbnail=thumbnail,
    )


class BoschCameraMediaSource(MediaSource):
    name = "Bosch Camera"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        if not item.identifier:
            raise Unresolvable("Cannot play the root folder")
        url = f"{URL_PREFIX}/{item.identifier}"
        mime, _ = mimetypes.guess_type(item.identifier)
        return PlayMedia(url, mime or "application/octet-stream")

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        try:
            return await self.hass.async_add_executor_job(
                self._browse, item.identifier or ""
            )
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

    # ── browse dispatch ──────────────────────────────────────────────────────
    def _browse(self, identifier: str) -> BrowseMediaSource:
        sources = _enabled_sources(self.hass)
        if not sources:
            return _node(identifier="", title=self.name, children=[])

        # Group by entry to drive root-level skipping.
        by_entry: dict[str, list[tuple[_Source, Any]]] = {}
        for src, b in sources:
            by_entry.setdefault(src.entry_id, []).append((src, b))

        if not identifier:
            entry_ids = list(by_entry.keys())
            if len(entry_ids) == 1:
                only_entry = entry_ids[0]
                return self._browse_entry_root(
                    only_entry, by_entry[only_entry], root=True
                )
            children = [
                _node(
                    identifier=eid,
                    title=_entry_title(self.hass, eid),
                )
                for eid in entry_ids
            ]
            return _node(identifier="", title=self.name, children=children)

        parts = identifier.split("/")
        entry_id = parts[0]
        if entry_id not in by_entry:
            raise Unresolvable(f"Unknown entry: {entry_id}")

        # Entry root view (lists sources if more than one)
        if len(parts) == 1:
            return self._browse_entry_root(entry_id, by_entry[entry_id], root=False)

        # Identifiers under a single-source entry omit the source token (the
        # tree skips the chooser level), so parts[1] is already a tree segment
        # (year for SMB / camera for local / camera for NVR). Detect that case
        # and pick the source implicitly from the entry's only backend.
        # Use the actual backend kind to distinguish a bare tree-segment from a
        # source-kind token — this handles backwards-compatible bookmarks
        # (old multi-source identifiers like "{entry_id}/L/cam") while also
        # working correctly for camera names that coincidentally equal "L"/"S"/"N".
        single_source = len(by_entry[entry_id]) == 1
        actual_kind = by_entry[entry_id][0][0].kind if single_source else None
        if single_source and parts[1] != actual_kind:
            src, backend = by_entry[entry_id][0]
            rest = parts[1:]
        else:
            kind = parts[1]
            match = _find_source(self.hass, entry_id, kind)
            if match is None:
                raise Unresolvable(f"Unknown source kind: {kind}")
            src, backend = match
            rest = parts[2:]

        if isinstance(backend, _LocalBackend):
            return self._browse_local(src, backend, rest, single_source=single_source)
        if isinstance(backend, _NvrBackend):
            return self._browse_nvr(src, backend, rest, single_source=single_source)
        return self._browse_smb(src, backend, rest, single_source=single_source)

    def _browse_entry_root(
        self,
        entry_id: str,
        sources_for_entry: list[tuple[_Source, Any]],
        *,
        root: bool,
    ) -> BrowseMediaSource:
        if len(sources_for_entry) == 1:
            src, backend = sources_for_entry[0]
            if isinstance(backend, _LocalBackend):
                return self._browse_local(
                    src, backend, [], single_source=True, root=root
                )
            if isinstance(backend, _NvrBackend):
                return self._browse_nvr(src, backend, [], single_source=True, root=root)
            return self._browse_smb(src, backend, [], single_source=True, root=root)

        children = [
            _node(
                identifier=f"{entry_id}/{src.kind}",
                title=src.label,
            )
            for src, _ in sources_for_entry
        ]
        title = self.name if root else _entry_title(self.hass, entry_id)
        return _node(
            identifier="" if root else entry_id,
            title=title,
            children=children,
        )

    # ── local backend tree ──────────────────────────────────────────────────
    # camera_first=True  → camera / year / month / day / events  (5 levels)
    # camera_first=False → camera / date / events                (3 levels, legacy)
    # Driven by backend.folder_pattern (same option as NAS uploads).
    def _browse_local(
        self,
        src: _Source,
        backend: _LocalBackend,
        rest: list[str],
        *,
        single_source: bool,
        root: bool = False,
    ) -> BrowseMediaSource:
        prefix = src.entry_id if single_source else f"{src.entry_id}/{src.kind}"

        def ident(*parts: str) -> str:
            return "/".join((prefix, *parts)) if parts else prefix

        title_root = (
            self.name
            if root
            else (_entry_title(self.hass, src.entry_id) if single_source else src.label)
        )

        # cameras level (shared by both modes)
        if not rest:
            children = [
                _node(identifier=ident(cam), title=cam)
                for cam in backend.list_cameras()
            ]
            return _node(
                identifier="" if root else prefix, title=title_root, children=children
            )

        camera = rest[0]

        if backend.camera_first:
            if len(rest) == 1:  # years + any flat dates (files directly in camera/)
                children = [
                    _node(identifier=ident(camera, y), title=y)
                    for y in backend.list_years(camera)
                ]
                for d in backend.list_dates(camera):
                    children.append(_node(identifier=ident(camera, d), title=d))
                return _node(identifier=ident(camera), title=camera, children=children)
            if len(rest) == 2:  # months or flat-date events
                year = rest[1]
                if _YEAR_RE.match(year):
                    children = [
                        _node(identifier=ident(camera, year, m), title=m)
                        for m in backend.list_months(camera, year)
                    ]
                    return _node(
                        identifier=ident(camera, year), title=year, children=children
                    )
                # rest[1] is a full "YYYY-MM-DD" date → flat events in camera/ folder
                date = year
                children = []
                for fname, image, parsed in backend.list_events(camera, date):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = f"{URL_PREFIX}/{ident(camera, image)}" if image else None
                    children.append(
                        _node(
                            identifier=ident(camera, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(camera, date),
                    title=date,
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )
            if len(rest) == 3:  # days
                year, month = rest[1], rest[2]
                children = [
                    _node(identifier=ident(camera, year, month, d), title=d)
                    for d in backend.list_days(camera, year, month)
                ]
                return _node(
                    identifier=ident(camera, year, month),
                    title=month,
                    children=children,
                )
            if len(rest) == 4:  # events
                year, month, day = rest[1], rest[2], rest[3]
                children = []
                for fname, image, parsed in backend.list_events_dated(
                    camera, year, month, day
                ):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = (
                        f"{URL_PREFIX}/{ident(camera, year, month, day, image)}"
                        if image
                        else None
                    )
                    children.append(
                        _node(
                            identifier=ident(camera, year, month, day, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(camera, year, month, day),
                    title=day,
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )
        else:
            # legacy flat: camera → date → events
            if len(rest) == 1:
                children = [
                    _node(identifier=ident(camera, d), title=d)
                    for d in backend.list_dates(camera)
                ]
                return _node(identifier=ident(camera), title=camera, children=children)
            if len(rest) == 2:
                date = rest[1]
                children = []
                for fname, image, parsed in backend.list_events(camera, date):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = f"{URL_PREFIX}/{ident(camera, image)}" if image else None
                    children.append(
                        _node(
                            identifier=ident(camera, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(camera, date),
                    title=date,
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )

        raise Unresolvable(f"Cannot browse: {'/'.join(rest)}")

    # ── nvr backend tree (camera/date/segment) ──────────────────────────────
    def _browse_nvr(
        self,
        src: _Source,
        backend: _NvrBackend,
        rest: list[str],
        *,
        single_source: bool,
        root: bool = False,
    ) -> BrowseMediaSource:
        prefix = src.entry_id if single_source else f"{src.entry_id}/{src.kind}"

        def ident(*parts: str) -> str:
            return "/".join((prefix, *parts)) if parts else prefix

        if not rest:
            children = [
                _node(identifier=ident(cam), title=cam)
                for cam in backend.list_cameras()
            ]
            title = (
                self.name
                if root
                else (
                    _entry_title(self.hass, src.entry_id)
                    if single_source
                    else src.label
                )
            )
            return _node(
                identifier="" if root else prefix,
                title=title,
                children=children,
            )

        camera = rest[0]
        if len(rest) == 1:
            children = [
                _node(identifier=ident(camera, d), title=d)
                for d in backend.list_dates(camera)
            ]
            return _node(identifier=ident(camera), title=camera, children=children)

        if len(rest) == 2:
            date = rest[1]
            children = []
            for fname, label in backend.list_segments(camera, date):
                children.append(
                    _node(
                        identifier=ident(camera, date, fname),
                        title=label,
                        media_class=MediaClass.VIDEO,
                        media_content_type="video/mp4",
                        can_play=True,
                        can_expand=False,
                    )
                )
            return _node(
                identifier=ident(camera, date),
                title=date,
                children=children,
                children_media_class=MediaClass.VIDEO,
            )

        raise Unresolvable(f"Cannot browse: {'/'.join(rest)}")

    # ── smb backend tree ────────────────────────────────────────────────────────
    # camera_first=True  → camera / year / month / day / event  (5 levels)
    # camera_first=False → year / month / day / event           (4 levels, legacy)
    # Determined by backend.folder_pattern (read from options: folder_pattern).
    def _browse_smb(
        self,
        src: _Source,
        backend: _SmbBackend,
        rest: list[str],
        *,
        single_source: bool,
        root: bool = False,
    ) -> BrowseMediaSource:
        """Render one SMB tree node, sharing ONE SMB session across every
        directory-listing call this single browse step makes.

        A single node can need 1-2 sequential `scandir` calls (e.g. the
        "years + flat dates" probe at the camera level tries both
        `list_years` and `list_flat_dates`) — each used to be a brand-new
        TCP+SMB2-session handshake. `_SmbBackend`'s per-call-cache design
        (see its class docstring) exists to stop *concurrent* callers (HTTP
        Range-request streaming via open_file/open_flat_file — untouched
        here, still per-call) from starving one connection's SMB2 credit
        pool; reusing a cache across a handful of *sequential* listing calls
        within one browse() invocation doesn't hit that failure mode, and
        the cache is still closed at the end of this method — it never
        outlives a single browse step.
        """
        session = backend._new_session_cache()
        try:
            return self._browse_smb_inner(
                src, backend, rest, session, single_source=single_source, root=root
            )
        finally:
            backend._close_session_cache(session)

    def _browse_smb_inner(
        self,
        src: _Source,
        backend: _SmbBackend,
        rest: list[str],
        session: dict[str, Any],
        *,
        single_source: bool,
        root: bool = False,
    ) -> BrowseMediaSource:
        prefix = src.entry_id if single_source else f"{src.entry_id}/{src.kind}"

        def ident(*parts: str) -> str:
            return "/".join((prefix, *parts)) if parts else prefix

        title_root = (
            self.name
            if root
            else (_entry_title(self.hass, src.entry_id) if single_source else src.label)
        )

        if backend.camera_first:
            # ── camera-first: root → cameras ──
            if not rest:
                children = [
                    _node(identifier=ident(cam), title=cam)
                    for cam in backend.list_cameras(session=session)
                ]
                return _node(
                    identifier="" if root else prefix,
                    title=title_root,
                    children=children,
                )
            if len(rest) == 1:  # years + any flat dates (files directly in camera/)
                camera = rest[0]
                if _YEAR_RE.match(camera):
                    # Year-first folder: camera IS the year — show months directly
                    children = [
                        _node(identifier=ident(camera, m), title=m)
                        for m in backend.list_year_first_months(camera, session=session)
                    ]
                    return _node(
                        identifier=ident(camera), title=camera, children=children
                    )
                children = [
                    _node(identifier=ident(camera, y), title=y)
                    for y in backend.list_years(camera, session=session)
                ]
                for d in backend.list_flat_dates(camera, session=session):
                    children.append(_node(identifier=ident(camera, d), title=d))
                return _node(identifier=ident(camera), title=camera, children=children)
            if len(rest) == 2:  # months or flat-date events
                camera, year = rest[0], rest[1]
                if _YEAR_RE.match(camera) and _DATE_DIR_RE.match(year):
                    # Year-first: camera=YYYY, year=MM — show days
                    actual_year, month = camera, year
                    children = [
                        _node(identifier=ident(actual_year, month, d), title=d)
                        for d in backend.list_year_first_days(
                            actual_year, month, session=session
                        )
                    ]
                    return _node(
                        identifier=ident(actual_year, month),
                        title=f"{actual_year}-{month}",
                        children=children,
                    )
                if _YEAR_RE.match(year):
                    children = [
                        _node(identifier=ident(camera, year, m), title=m)
                        for m in backend.list_months(camera, year, session=session)
                    ]
                    return _node(
                        identifier=ident(camera, year), title=year, children=children
                    )
                # rest[1] is a full "YYYY-MM-DD" date → flat events in camera/ folder
                date = year
                children = []
                for fname, image, parsed in backend.list_flat_events(
                    camera, date, session=session
                ):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = f"{URL_PREFIX}/{ident(camera, image)}" if image else None
                    children.append(
                        _node(
                            identifier=ident(camera, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(camera, date),
                    title=date,
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )
            if len(rest) == 3:  # days or year-first events
                camera, year, month = rest
                if (
                    _YEAR_RE.match(camera)
                    and _DATE_DIR_RE.match(year)
                    and _DATE_DIR_RE.match(month)
                ):
                    # Year-first: camera=YYYY, year=MM, month=DD — show events
                    actual_year, actual_month, day = camera, year, month
                    children = []
                    for fname, image, parsed in backend.list_year_first_events(
                        actual_year, actual_month, day, session=session
                    ):
                        ext = fname.rsplit(".", 1)[-1].lower()
                        mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                        mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                        thumb = (
                            f"{URL_PREFIX}/{ident(actual_year, actual_month, day, image)}"
                            if image
                            else None
                        )
                        children.append(
                            _node(
                                identifier=ident(actual_year, actual_month, day, fname),
                                title=_format_event_title(parsed),
                                media_class=mc,
                                media_content_type=mime,
                                can_play=True,
                                can_expand=False,
                                thumbnail=thumb,
                            )
                        )
                    return _node(
                        identifier=ident(actual_year, actual_month, day),
                        title=f"{actual_year}-{actual_month}-{day}",
                        children=children,
                        children_media_class=MediaClass.VIDEO,
                    )
                children = [
                    _node(identifier=ident(camera, year, month, d), title=d)
                    for d in backend.list_days(camera, year, month, session=session)
                ]
                return _node(
                    identifier=ident(camera, year, month),
                    title=month,
                    children=children,
                )
            if len(rest) == 4:  # events
                camera, year, month, day = rest
                children = []
                for fname, image, parsed in backend.list_events(
                    camera, year, month, day, session=session
                ):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = (
                        f"{URL_PREFIX}/{ident(camera, year, month, day, image)}"
                        if image
                        else None
                    )
                    children.append(
                        _node(
                            identifier=ident(camera, year, month, day, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(camera, year, month, day),
                    title=day,
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )
        else:
            # ── date-first (legacy): root → years ──
            # camera arg is "" (filtered by _path so path traversal is correct)
            if not rest:
                children = [
                    _node(identifier=ident(y), title=y)
                    for y in backend.list_years("", session=session)
                ]
                return _node(
                    identifier="" if root else prefix,
                    title=title_root,
                    children=children,
                )
            if len(rest) == 1:  # months
                year = rest[0]
                children = [
                    _node(identifier=ident(year, m), title=m)
                    for m in backend.list_months("", year, session=session)
                ]
                return _node(identifier=ident(year), title=year, children=children)
            if len(rest) == 2:  # days
                year, month = rest
                children = [
                    _node(identifier=ident(year, month, d), title=f"{year}-{month}-{d}")
                    for d in backend.list_days("", year, month, session=session)
                ]
                return _node(
                    identifier=ident(year, month),
                    title=f"{year}-{month}",
                    children=children,
                )
            if len(rest) == 3:  # events
                year, month, day = rest
                children = []
                for fname, image, parsed in backend.list_events(
                    "", year, month, day, session=session
                ):
                    ext = fname.rsplit(".", 1)[-1].lower()
                    mime = "video/mp4" if ext == "mp4" else "image/jpeg"
                    mc = MediaClass.VIDEO if ext == "mp4" else MediaClass.IMAGE
                    thumb = (
                        f"{URL_PREFIX}/{ident(year, month, day, image)}"
                        if image
                        else None
                    )
                    children.append(
                        _node(
                            identifier=ident(year, month, day, fname),
                            title=_format_event_title(parsed),
                            media_class=mc,
                            media_content_type=mime,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumb,
                        )
                    )
                return _node(
                    identifier=ident(year, month, day),
                    title=f"{year}-{month}-{day}",
                    children=children,
                    children_media_class=MediaClass.VIDEO,
                )

        raise Unresolvable(f"Cannot browse: {'/'.join(rest)}")


# ── HTTP view ────────────────────────────────────────────────────────────────
class BoschCameraMediaView(HomeAssistantView):
    """Serve event jpg/mp4 files from local FS or via SMB. Auth required."""

    name = f"api:{DOMAIN}:event"
    url = URL_PREFIX + "/{entry_id}/{location:.*}"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, location: str
    ) -> web.StreamResponse:
        parts = [p for p in location.split("/") if p]
        if not parts:
            raise web.HTTPNotFound

        # Identifier shapes (with optional source token):
        #   {entry_id}/L/{camera}/{filename}                       (local, multi-source)
        #   {entry_id}/{camera}/{filename}                         (local, single-source)
        #   {entry_id}/S/{camera}/{Y}/{M}/{D}/{filename}           (smb, multi-source)
        #   {entry_id}/{camera}/{Y}/{M}/{D}/{filename}             (smb, single-source)
        #   {entry_id}/N/{camera}/{YYYY-MM-DD}/{file}.mp4          (nvr, multi-source)
        #   {entry_id}/{camera}/{YYYY-MM-DD}/{file}.mp4            (nvr, single-source)
        head = parts[0]
        if head in ("L", "S", "N"):
            kind = head
            tail = parts[1:]
        elif _YEAR_RE.match(head):
            # year/month/day/filename → SMB date-first single-source
            kind = "S"
            tail = parts
        elif len(parts) >= 2 and _YEAR_RE.match(parts[1]):
            # camera/year/month/day/filename — Local OR SMB camera-first single-source.
            # Prefer SMB only when an SMB source is actually configured; otherwise this
            # is a Local camera-first path (folder_pattern={camera}/{year}/{month}/{day}).
            kind = (
                "S"
                if await self.hass.async_add_executor_job(
                    _find_source, self.hass, entry_id, "S"
                )
                is not None
                else "L"
            )
            tail = parts
        elif len(parts) >= 3 and _NVR_DATE_DIR_RE.match(parts[1]):
            # camera/YYYY-MM-DD/HH-MM.mp4 → NVR single-source.
            kind = "N"
            tail = parts
        else:
            # Flat file in camera/ folder — Local or SMB flat single-source.
            # Prefer Local if a Local source is configured; fall back to SMB
            # so that users with only an SMB share (no local download_path) still
            # get their flat NAS files served correctly.
            kind = (
                "L"
                if await self.hass.async_add_executor_job(
                    _find_source, self.hass, entry_id, "L"
                )
                is not None
                else "S"
            )
            tail = parts

        # Regression (bug-hunt 2026-07-03): _find_source → _enabled_sources
        # does blocking Path.exists()/mkdir()/is_dir() per configured entry.
        # _browse() below already wraps this in async_add_executor_job; this
        # HTTP GET handler (hit once per served file/thumbnail — a day-folder
        # view can fire ~200+ of these) called it directly on the event loop.
        match = await self.hass.async_add_executor_job(
            _find_source, self.hass, entry_id, kind
        )
        if match is None:
            raise web.HTTPNotFound
        _src, backend = match

        if isinstance(backend, _LocalBackend):
            if len(tail) not in (2, 4, 5):
                raise web.HTTPNotFound
            return await self._serve_local(request, backend, *tail)

        if isinstance(backend, _NvrBackend):
            if len(tail) != 3:
                raise web.HTTPNotFound
            camera, date, filename = tail
            return await self._serve_nvr(request, backend, camera, date, filename)

        if len(tail) == 5:
            camera, year, month, day, filename = tail
        elif len(tail) == 4:
            # date-first single-source or legacy URLs
            year, month, day, filename = tail
            camera = ""
        elif len(tail) == 2:
            # flat file directly in camera/ folder
            camera, filename = tail
            return await self._serve_smb_flat(request, backend, camera, filename)
        else:
            raise web.HTTPNotFound
        return await self._serve_smb(
            request, backend, camera, year, month, day, filename
        )

    # local path → web.FileResponse handles Range natively
    # segments: (camera, filename) for flat mode or (camera, year, month, day, filename) for camera-first
    async def _serve_local(
        self, request: web.Request, backend: _LocalBackend, *segments: str
    ) -> web.StreamResponse:
        filename = segments[-1]
        if not _parse_filename(filename):
            raise web.HTTPNotFound
        path = await self.hass.async_add_executor_job(backend.resolve, *segments)
        if path is None:
            raise web.HTTPNotFound
        mime, _ = mimetypes.guess_type(str(path))
        if mime not in ("image/jpeg", "video/mp4"):
            raise web.HTTPNotFound
        return web.FileResponse(path)

    # nvr path → web.FileResponse handles Range natively (mp4 only)
    async def _serve_nvr(
        self,
        request: web.Request,
        backend: _NvrBackend,
        camera: str,
        date: str,
        filename: str,
    ) -> web.StreamResponse:
        if not _NVR_DATE_DIR_RE.match(date) or not _NVR_SEG_RE.match(filename):
            raise web.HTTPNotFound
        path = await self.hass.async_add_executor_job(
            backend.resolve,
            camera,
            date,
            filename,
        )
        if path is None:
            raise web.HTTPNotFound
        return web.FileResponse(path)

    # smb path → manual stream with Range support
    async def _serve_smb(
        self,
        request: web.Request,
        backend: _SmbBackend,
        camera: str,
        year: str,
        month: str,
        day: str,
        filename: str,
    ) -> web.StreamResponse:
        if not (
            _YEAR_RE.match(year)
            and _DATE_DIR_RE.match(month)
            and _DATE_DIR_RE.match(day)
        ):
            raise web.HTTPNotFound
        try:
            fobj, size = await self.hass.async_add_executor_job(
                backend.open_file, camera, year, month, day, filename
            )
        except FileNotFoundError as err:
            raise web.HTTPNotFound from err
        except OSError as err:
            _LOGGER.warning(
                "SMB open failed for %s/%s/%s/%s/%s: %s",
                camera,
                year,
                month,
                day,
                filename,
                err,
            )
            raise web.HTTPNotFound from err
        return await self._stream_smb_fobj(request, fobj, size, filename)

    async def _serve_smb_flat(
        self,
        request: web.Request,
        backend: _SmbBackend,
        camera: str,
        filename: str,
    ) -> web.StreamResponse:
        if not _parse_filename(filename):
            raise web.HTTPNotFound
        try:
            fobj, size = await self.hass.async_add_executor_job(
                backend.open_flat_file, camera, filename
            )
        except FileNotFoundError as err:
            raise web.HTTPNotFound from err
        except OSError as err:
            _LOGGER.warning("SMB flat open failed for %s/%s: %s", camera, filename, err)
            raise web.HTTPNotFound from err
        return await self._stream_smb_fobj(request, fobj, size, filename)

    async def _stream_smb_fobj(
        self, request: web.Request, fobj: Any, size: int, filename: str
    ) -> web.StreamResponse:
        try:
            mime, _ = mimetypes.guess_type(filename)
            mime = mime or "application/octet-stream"

            start, end = 0, size - 1
            status = 200
            range_header = request.headers.get("Range", "")
            if range_header.startswith("bytes="):
                spec = range_header[6:].strip()
                s, _, e = spec.partition("-")
                try:
                    if s:
                        start = int(s)
                    if e:
                        end = min(int(e), size - 1)
                    if 0 <= start <= end < size:
                        status = 206
                    else:
                        start, end, status = 0, size - 1, 200
                except ValueError:
                    start, end, status = 0, size - 1, 200

            length = end - start + 1
            headers = {
                "Content-Type": mime,
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            }
            if status == 206:
                headers["Content-Range"] = f"bytes {start}-{end}/{size}"

            response = web.StreamResponse(status=status, headers=headers)
            await response.prepare(request)

            if start > 0:
                await self.hass.async_add_executor_job(fobj.seek, start)
            remaining = length
            while remaining > 0:
                chunk_size = min(remaining, _CHUNK)
                chunk = await self.hass.async_add_executor_job(fobj.read, chunk_size)
                if not chunk:
                    break
                await response.write(chunk)
                remaining -= len(chunk)
            await response.write_eof()
            return response
        finally:
            close_cache = getattr(fobj, "_bosch_close_cache", None)
            try:
                await self.hass.async_add_executor_job(fobj.close)
            finally:
                if close_cache is not None:
                    try:
                        await self.hass.async_add_executor_job(close_cache)
                    except Exception:  # pragma: no cover — best-effort async cache teardown, failure non-actionable
                        pass
