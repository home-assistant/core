"""SMB/NAS upload and auto-download helpers for Bosch Smart Home Camera.

Extracted from __init__.py to keep the coordinator lean.
All functions that previously used `self` now take a `coordinator` parameter.
"""

import calendar
import contextlib
from datetime import UTC
import logging
import os
import re
import socket
import ssl
import threading
import time
from typing import TYPE_CHECKING, Any
import urllib.error
from urllib.parse import urlparse
import urllib.request

if TYPE_CHECKING:
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


# ── URL allowlist for image/video downloads (SSRF prevention) ────────────────
_SAFE_DOMAINS = frozenset({".boschsecurity.com", ".bosch.com"})


def _is_safe_bosch_url(url: str) -> bool:
    """Validate that a URL points to a known Bosch domain (HTTPS only)."""
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and any(parsed.hostname.endswith(d) for d in _SAFE_DOMAINS)
    )


_SSL_CTX: ssl.SSLContext | None = None
_SSL_CTX_LOCK = threading.Lock()


def _bosch_ssl_ctx() -> ssl.SSLContext:
    """Return a verifying SSL context that pins the Bosch private cloud CA.

    Cloud media downloads (imageUrl / videoClipUrl on ``*.boschsecurity.com``)
    carry the bearer token in the Authorization header, so TLS MUST be verified
    to prevent MITM (CWE-295 / GHSA-6qh5-x5m5-vj6v). Reuses the same pinned
    context as cloud_ssl (system roots + Bosch intermediate via
    VERIFY_X509_PARTIAL_CHAIN) instead of the former CERT_NONE.

    Cached at module level: building loads the system CA bundle (blocking I/O),
    and all smb callers run in an executor thread, so the one-off blocking build
    is acceptable. The LAN/self-signed exception applies only to camera IPs,
    never to the cloud host reached here.
    """
    global _SSL_CTX  # noqa: PLW0603 -- lazy process-lifetime singleton cache
    if _SSL_CTX is None:
        # Imported lazily to avoid any package import-order coupling.
        from .cloud_ssl import _build_ssl_context

        with _SSL_CTX_LOCK:
            if _SSL_CTX is None:
                _SSL_CTX = _build_ssl_context()
    return _SSL_CTX


def _http_get(
    url: str, token: str, timeout: int = 60, stream: bool = False
) -> tuple[int, bytes]:
    """Download *url* using stdlib urllib (no third-party dependency).

    Returns (status_code, body_bytes).  For streaming downloads use
    _http_get_chunked() instead so memory stays bounded.
    If the request fails with a network error, raises urllib.error.URLError or OSError.
    """
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url
    with (
        urllib.request.urlopen(req, context=_bosch_ssl_ctx(), timeout=timeout) as r
    ):  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url
        return r.status, r.read()


def _http_get_to_file(url: str, token: str, dest_path: str, timeout: int = 60) -> bool:
    """Stream *url* content to *dest_path* (create parent dirs first).

    Returns True on success (HTTP 200), False on non-200.
    Raises urllib.error.URLError / OSError on network failure.
    """
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url
    with (
        urllib.request.urlopen(req, context=_bosch_ssl_ctx(), timeout=timeout) as r
    ):  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url
        if r.status != 200:
            return False
        with open(dest_path, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    return True


def _http_get_chunked(url: str, token: str, timeout: int = 60) -> Any:
    """Context manager yielding raw urllib response for chunked reads.

    Usage::
        with _http_get_chunked(url, token) as r:
            if r.status == 200:
                while chunk := r.read(65536):
                    ...
    """
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url
    return urllib.request.urlopen(
        req, context=_bosch_ssl_ctx(), timeout=timeout
    )  # Bosch cloud URL, https+bearer, caller must validate via _is_safe_bosch_url


def smb_available() -> bool:
    """Return True if the optional ``smbprotocol``/``smbclient`` package is importable.

    ``smbprotocol`` ships as a `manifest.json` requirement, so under a normal
    HACS install it's always present — this only returns False if pip's
    install of that requirement failed (e.g. an unsupported OS/architecture
    wheel) or the package was removed post-install. Every SMB call site in
    this module already degrades gracefully on ``ImportError`` (logs a
    warning and returns/no-ops instead of crashing); this helper lets
    integration-wide callers (coordinator Repairs-issue check, media_source's
    SMB browse backend) make the same "is it actually usable" decision
    without duplicating a bare ``try/except ImportError`` themselves.
    """
    try:
        import smbclient
    except ImportError:
        return False
    return True


def smb_dependent_features(opts: dict[str, Any]) -> list[str]:
    """Return English labels of currently-configured SMB-dependent features.

    A feature is "SMB-dependent" only when its storage/upload target is
    actually set to ``smb`` — FTP and Local targets reuse the same
    ``enable_smb_upload``/``enable_nvr`` toggles but never touch
    ``smbclient``, so they're excluded here.

    Shared source of truth for two callers that both need to know "does the
    currently-configured feature set actually require smbprotocol":
    ``__init__.py``'s per-coordinator-tick Repairs-issue check
    (``_refresh_smb_unavailable_issue``) and ``config_flow.py``'s options-flow
    save handler (which raises the same issue immediately on save, so the
    user gets feedback in the same request instead of waiting for the next
    tick).
    """
    features: list[str] = []
    if (
        opts.get("enable_smb_upload")
        and (opts.get("upload_protocol") or "smb").lower() == "smb"
    ):
        features.append("SMB event upload")
    if (
        opts.get("enable_nvr")
        and (opts.get("nvr_storage_target") or "local").lower() == "smb"
    ):
        features.append("Mini-NVR SMB storage")
    return features


def _safe_name(name: str) -> str:
    """Sanitize a camera name for use as a directory/file name component.

    Removes path traversal sequences and non-safe characters, truncates to 64 chars.
    """
    return re.sub(r"[^\w\-. ]", "_", name.replace("..", "_"))[:64]


# ── Local save (FCM-triggered, runs in executor thread) ───────────────────────


def sync_local_save(
    coordinator: BoschCameraCoordinator, ev: dict[str, Any], token: str, cam_name: str
) -> None:
    """Save a single event's image/clip to the local download_path on FCM trigger.

    Folder structure follows folder_pattern option (default: {camera}/{year}/{month}/{day}).
    Filename follows file_pattern option (default: {camera}_{date}_{time}_{type}_{id}).
    """
    opts = coordinator.options
    if not opts.get("enable_local_save"):
        return
    download_path = (opts.get("download_path") or "").strip()
    if not download_path:
        return

    ts = ev.get("timestamp", "")
    if not ts or len(ts) < 19:
        return

    # Reject events that predate this coordinator session (e.g. delayed/queued
    # FCM pushes arriving after a reload). Parse ISO timestamp → epoch and
    # compare against coordinator._download_started_at (set at __init__ time).
    # Allow 60 s of slack for clock skew and network/processing delay.
    started_at = getattr(coordinator, "_download_started_at", 0.0)
    if started_at:
        try:
            struct = time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
            ev_epoch = calendar.timegm(struct)
            if ev_epoch < started_at - 60:
                _LOGGER.debug(
                    "Local save skipped: event %s predates session start (%.0fs old at startup)",
                    ts[:19],
                    started_at - ev_epoch,
                )
                return
        except Exception:  # timestamp parse failure is non-actionable; event proceeds without age-filter
            pass

    cam_safe = _safe_name(cam_name)
    date_str = ts[:10]
    time_str = ts[11:19].replace(":", "-")
    etype = ev.get("eventType", "EVENT")
    ev_id = (ev.get("id") or "")[:8].upper()

    year, month, day = date_str[:4], date_str[5:7], date_str[8:10]
    folder_pattern = (
        (opts.get("folder_pattern") or "{camera}/{year}/{month}/{day}")
        .strip()
        .strip("/")
    )
    file_pattern = (
        opts.get("file_pattern") or "{camera}_{date}_{time}_{type}_{id}"
    ).strip()

    try:
        sub = folder_pattern.format(
            camera=cam_safe,
            year=year,
            month=month,
            day=day,
            date=date_str,
            time=time_str,
            type=etype,
        )
    except KeyError, ValueError:
        sub = cam_safe

    folder = os.path.join(download_path, sub.replace("/", os.sep))

    try:
        stem = file_pattern.format(
            camera=cam_safe,
            date=date_str,
            time=time_str,
            type=etype,
            id=ev_id,
            year=year,
            month=month,
            day=day,
        )
    except KeyError, ValueError:
        stem = f"{cam_safe}_{date_str}_{time_str}_{etype}_{ev_id}"

    for ext, url in [("jpg", ev.get("imageUrl")), ("mp4", ev.get("videoClipUrl"))]:
        if not url:
            continue
        if ext == "mp4" and ev.get("videoClipUploadStatus") != "Done":
            continue
        if not _is_safe_bosch_url(url):
            continue
        path = os.path.join(folder, f"{stem}.{ext}")
        if os.path.exists(path):
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            ok = _http_get_to_file(url, token, path, timeout=60)
            if ok:
                _LOGGER.debug("Local save: %s", os.path.basename(path))
        except Exception as err:
            _LOGGER.warning("Local save failed for %s: %s", os.path.basename(path), err)


# ── SMB/NAS upload (runs in executor thread) ──────────────────────────────────

# Bounds every blocking smbclient/smbprotocol socket op during the actual
# transfer loop below (separate from the 10s connection-setup timeout used for
# register_session). smbprotocol has no per-call timeout parameter of its own
# — it relies on the stdlib socket module's default timeout — so this is the
# only lever available short of a hard executor-thread kill (which Python
# cannot do). The caller (fcm.py async_handle_fcm_push) wraps this whole
# executor job in `asyncio.wait_for(..., timeout=30.0)`, but that only
# abandons the *await* — it cannot stop the underlying thread, so a hang here
# without its own socket timeout would leak the thread forever. This timeout
# is deliberately shorter than that 30s so a hung op fails and unwinds via the
# normal per-transfer try/except *before* the outer wait_for gives up — the
# outer wait_for is now just a safety margin, not the real cutoff.
_SMB_TRANSFER_TIMEOUT = 20.0

# socket.setdefaulttimeout() is PROCESS-GLOBAL, not per-thread — it affects
# every new socket created anywhere in the process, on any thread, for as
# long as it's set. Multiple cameras can each trigger a concurrent FCM push
# (async_add_executor_job runs sync_smb_upload on HA's shared executor pool),
# so without serialization two overlapping calls can race on the default:
# thread B's `finally: socket.setdefaulttimeout(None)` can fire while thread
# A is still mid-transfer, silently stripping A's timeout protection (or vice
# versa for the register_session 10s window below). This lock makes the
# whole "mutate default → do blocking I/O → restore default" span atomic
# across threads so one call's cleanup can never undo another's in-flight
# timeout.
_SOCKET_TIMEOUT_LOCK = threading.Lock()


def sync_smb_upload(
    coordinator: BoschCameraCoordinator,
    data: dict[str, Any],
    token: str,
    prefetched_image: bytes | None = None,
) -> None:
    """Upload new event files to SMB or FTP.

    Folder structure: {smb_base_path}/{camera}/{year}/{month}/{day}/{camera_name}_{date}_{time}_{type}.{ext}
    Backend selected via ``upload_protocol`` option ("smb" default, or "ftp").

    ``prefetched_image`` — when provided, use these bytes directly for the
    snapshot upload instead of downloading from imageUrl.  The caller
    (async_send_alert in fcm.py) passes the already-downloaded step-2 bytes to
    avoid an extra Bosch cloud pull during an active RTSP live-stream — both
    transfers would compete on the camera's single TLS control channel, causing
    RTSP keepalive latency spikes and 5-10 s stream freezes.
    Source: knowledge-base/stream-freeze-on-motion-event-contention.md
    """
    protocol = (coordinator.options.get("upload_protocol") or "smb").lower()
    if protocol == "ftp":
        _sync_ftp_upload(coordinator, data, token, prefetched_image)
        return

    opts = coordinator.options
    server = opts.get("smb_server", "").strip()
    share = opts.get("smb_share", "").strip()
    username = opts.get("smb_username", "").strip()
    password = opts.get("smb_password", "")

    if not opts.get("enable_smb_upload") or not server or not share:
        return

    try:
        from smbclient import open_file, register_session, stat as smb_stat
    except ImportError:
        _LOGGER.warning(
            "smbprotocol not installed — SMB upload disabled. "
            "Install with: pip install smbprotocol"
        )
        return

    # Held for the entire register_session()+transfer span below (see
    # _SOCKET_TIMEOUT_LOCK docstring) — socket.setdefaulttimeout() is
    # process-global, so a concurrent sync_smb_upload call for another
    # camera must not be allowed to reset it out from under this one.
    with _SOCKET_TIMEOUT_LOCK:
        try:
            socket.setdefaulttimeout(10)
            try:
                register_session(server, username=username, password=password)
            finally:
                socket.setdefaulttimeout(None)
        except Exception as err:
            _LOGGER.warning("SMB session to %s failed: %s", server, err)
            return

        # Bound the actual transfer below with its own socket timeout — see
        # _SMB_TRANSFER_TIMEOUT docstring above. Explicit per-call `timeout=`
        # kwargs on the urllib.request calls further down (clip downloads) take
        # precedence over this default and are unaffected.
        socket.setdefaulttimeout(_SMB_TRANSFER_TIMEOUT)
        try:
            _sync_smb_upload_events(
                coordinator, data, token, prefetched_image, open_file, smb_stat
            )
        finally:
            socket.setdefaulttimeout(None)


def _sync_smb_upload_events(
    coordinator: BoschCameraCoordinator,
    data: dict[str, Any],
    token: str,
    prefetched_image: bytes | None,
    open_file: Any,
    smb_stat: Any,
) -> None:
    """Per-event SMB transfer loop, run under _SMB_TRANSFER_TIMEOUT.

    Split out of sync_smb_upload purely so the socket-timeout `try/finally`
    scope (set right before this call) cleanly wraps only the actual transfer
    work, not the session setup above it.
    """
    opts = coordinator.options
    server = opts.get("smb_server", "").strip()
    share = opts.get("smb_share", "").strip()
    base_path = opts.get("smb_base_path", "Bosch-Kameras").strip()
    folder_pattern = opts.get("folder_pattern", "{camera}/{year}/{month}/{day}").strip()
    file_pattern = opts.get(
        "file_pattern", "{camera}_{date}_{time}_{type}_{id}"
    ).strip()

    for cam_id, cam_data in data.items():
        cam_name = _safe_name(cam_data["info"].get("title", cam_id))
        ev_list = cam_data.get("events", [])
        _LOGGER.debug("SMB upload: %s has %d events", cam_name, len(ev_list))

        for ev in ev_list:
            ts = ev.get("timestamp", "")
            if not ts or len(ts) < 19:
                _LOGGER.debug(
                    "SMB upload: skipping event with short/empty timestamp: %r", ts
                )
                continue

            # Parse timestamp for folder/file patterns
            year = ts[:4]
            month = ts[5:7]
            day = ts[8:10]
            date_str = f"{year}-{month}-{day}"
            time_str = ts[11:19].replace(":", "-")
            etype = ev.get("eventType", "EVENT")
            ev_id = ev.get("id", "")[:8]

            # Build folder path from pattern
            folder_parts = folder_pattern.format(
                year=year,
                month=month,
                day=day,
                camera=cam_name,
                type=etype,
            )
            smb_folder = f"\\\\{server}\\{share}\\{base_path}\\{folder_parts}"
            smb_folder = smb_folder.replace("/", "\\")

            # Build file name from pattern
            file_base = file_pattern.format(
                camera=cam_name,
                date=date_str,
                time=time_str,
                type=etype,
                id=ev_id,
                year=year,
                month=month,
                day=day,
            )

            # Ensure folder exists (create recursively)
            try:
                smb_makedirs(smb_folder, server, share, base_path, folder_parts)
            except Exception as err:
                _LOGGER.warning("SMB mkdir error for %s: %s", smb_folder, err)
                continue

            # Upload snapshot
            # Prefer prefetched_image bytes (already downloaded by the alert
            # pipeline in async_send_alert) to avoid a second Bosch cloud pull
            # while the RTSP live-stream is active on the camera's TLS channel.
            img_url = ev.get("imageUrl")
            _have_url = bool(img_url and _is_safe_bosch_url(img_url))
            if prefetched_image or _have_url:
                smb_path = f"{smb_folder}\\{file_base}.jpg"
                try:
                    smb_stat(smb_path)
                    _LOGGER.debug("SMB skip (exists): %s", file_base + ".jpg")
                except OSError:
                    try:
                        if prefetched_image:
                            # Use caller-supplied bytes — no extra cloud request.
                            content = prefetched_image
                            with open_file(smb_path, mode="wb") as f:
                                f.write(content)
                            _LOGGER.info(
                                "SMB uploaded (prefetched): %s (%d bytes)",
                                file_base + ".jpg",
                                len(content),
                            )
                        elif _have_url:
                            assert img_url is not None  # narrowed above
                            status, content = _http_get(img_url, token, timeout=30)
                            if status == 200 and content:
                                with open_file(smb_path, mode="wb") as f:
                                    f.write(content)
                                _LOGGER.info(
                                    "SMB uploaded: %s (%d bytes)",
                                    file_base + ".jpg",
                                    len(content),
                                )
                            else:
                                _LOGGER.warning(
                                    "SMB snapshot download failed: HTTP %d, %d bytes",
                                    status,
                                    len(content),
                                )
                    except Exception as err:
                        _LOGGER.warning("SMB upload error for %s: %s", file_base, err)
            else:
                _LOGGER.debug("SMB: no imageUrl for event %s", ev.get("id", "?")[:8])

            # Upload video clip
            clip_url = ev.get("videoClipUrl")
            clip_status = ev.get("videoClipUploadStatus", "")
            if clip_url and clip_status == "Done":
                if not _is_safe_bosch_url(clip_url):
                    _LOGGER.warning(
                        "SMB: skipping clip with non-Bosch URL: %s", clip_url
                    )
                    continue
                smb_path = f"{smb_folder}\\{file_base}.mp4"
                try:
                    smb_stat(smb_path)
                    _LOGGER.debug("SMB skip (exists): %s", file_base + ".mp4")
                except OSError:
                    try:
                        total = 0
                        req_obj = urllib.request.Request(  # Bosch cloud clip URL, https+bearer; guarded by _is_safe_bosch_url above
                            clip_url, headers={"Authorization": f"Bearer {token}"}
                        )
                        with (
                            urllib.request.urlopen(  # Bosch cloud clip URL, https+bearer; from Bosch API response (not user-supplied)
                                req_obj, context=_bosch_ssl_ctx(), timeout=60
                            ) as r
                        ):
                            if r.status == 200:
                                with open_file(smb_path, mode="wb") as f:
                                    while True:
                                        chunk = r.read(65536)
                                        if not chunk:
                                            break
                                        f.write(chunk)
                                        total += len(chunk)
                                _LOGGER.info(
                                    "SMB uploaded: %s (%d bytes)",
                                    file_base + ".mp4",
                                    total,
                                )
                            else:
                                _LOGGER.warning(
                                    "SMB clip download failed: HTTP %d", r.status
                                )
                    except Exception as err:
                        _LOGGER.warning(
                            "SMB clip upload error for %s: %s", file_base, err
                        )


def smb_makedirs(
    full_path: str, server: str, share: str, base_path: str, folder_parts: str
) -> None:
    """Create SMB directories recursively."""
    from smbclient import mkdir, stat as smb_stat

    # Build path incrementally
    parts = [
        p for p in f"{base_path}\\{folder_parts}".replace("/", "\\").split("\\") if p
    ]
    current = f"\\\\{server}\\{share}"

    for part in parts:
        current = f"{current}\\{part}"
        try:
            smb_stat(current)
        except OSError:
            with contextlib.suppress(OSError):  # may exist due to race condition
                mkdir(current)


# ── SMB retention cleanup (runs in executor thread, once per day) ─────────────


def sync_smb_cleanup(coordinator: BoschCameraCoordinator) -> None:
    """Delete files on the SMB or FTP share that are older than smb_retention_days."""
    protocol = (coordinator.options.get("upload_protocol") or "smb").lower()
    if protocol == "ftp":
        _sync_ftp_cleanup(coordinator)
        return
    try:
        from smbclient import register_session, remove, scandir, stat as smb_stat
    except ImportError:
        return

    opts = coordinator.options
    server = opts.get("smb_server", "").strip()
    share = opts.get("smb_share", "").strip()
    username = opts.get("smb_username", "").strip()
    password = opts.get("smb_password", "")
    base_path = opts.get("smb_base_path", "Bosch-Kameras").strip()
    retention_days = int(opts.get("smb_retention_days", 180))

    if (
        not opts.get("enable_smb_upload")
        or not server
        or not share
        or retention_days <= 0
    ):
        return

    try:
        socket.setdefaulttimeout(10)
        try:
            register_session(server, username=username, password=password)
        finally:
            socket.setdefaulttimeout(None)
    except Exception as err:
        _LOGGER.warning("SMB cleanup: session to %s failed: %s", server, err)
        return

    cutoff = time.time() - retention_days * 86400
    root = f"\\\\{server}\\{share}\\{base_path}"
    deleted = 0

    def _walk_and_delete(path: str) -> None:
        nonlocal deleted
        try:
            entries = list(scandir(path))
        except Exception:
            return
        for entry in entries:
            full = f"{path}\\{entry.name}"
            if entry.is_dir():
                _walk_and_delete(full)
            else:
                try:
                    st = smb_stat(full)
                    if st.st_mtime < cutoff:
                        remove(full)
                        deleted += 1
                        _LOGGER.debug("SMB cleanup: deleted %s", entry.name)
                except Exception as err:
                    _LOGGER.debug("SMB cleanup: error on %s: %s", entry.name, err)

    _walk_and_delete(root)
    if deleted:
        _LOGGER.info(
            "SMB cleanup: deleted %d file(s) older than %d days from %s",
            deleted,
            retention_days,
            root,
        )
        _fire_cleanup_alert(coordinator, deleted, retention_days, root)


# ── Cleanup alert (fires after age-based retention deletes files) ─────────────


def _fire_cleanup_alert(
    coordinator: BoschCameraCoordinator,
    deleted: int,
    retention_days: int,
    location: str,
) -> None:
    """Schedule a cleanup summary notification on the HA event loop (thread-safe)."""
    opts = coordinator.options
    system_raw = opts.get("alert_notify_system", "").strip()
    notify_service = system_raw or opts.get("alert_notify_service", "").strip()
    if not notify_service:
        return
    msg = (
        f"Bosch Kamera NAS: {deleted} Datei(en) älter als {retention_days} Tage "
        f"automatisch gelöscht ({location})"
    )
    coordinator.hass.loop.call_soon_threadsafe(
        coordinator.hass.async_create_task,
        _async_cleanup_alert(coordinator, msg, notify_service),
    )


async def _async_cleanup_alert(
    coordinator: BoschCameraCoordinator, message: str, notify_service: str
) -> None:
    """Send NAS retention summary via configured notify service."""
    for svc in [s.strip() for s in notify_service.split(",") if s.strip()]:
        domain, _, name = svc.partition(".")
        if coordinator.hass.services.has_service(domain, name):
            try:
                await coordinator.hass.services.async_call(
                    domain,
                    name,
                    {"message": message, "title": "Bosch Kamera — NAS-Bereinigung"},
                )
            except Exception as err:
                _LOGGER.debug("Cleanup alert via %s failed: %s", svc, err)
            else:
                return


# ── FTP backend (FRITZ.NAS, plain FTP servers) ────────────────────────────────
# FRITZ!Box SMB on macOS Sequoia hangs in `rename()` for minutes; FTP RNFR/RNTO
# is ~75 file/s on the same hardware. FTP backend reuses smb_* options
# (server / username / password / base_path / patterns); smb_share is unused
# because FTP has no shares — the base_path is relative to the FTP root.


def _ftp_connect(server: str, username: str, password: str) -> Any:
    """Open a passive-mode FTP connection. Caller closes via .quit()."""
    import ftplib

    ftp = ftplib.FTP(
        server, timeout=30
    )  # FTP ist eine bewusst konfigurierbare Upload-Zieloption (smb.py FTP-Pfad)
    ftp.login(username, password)
    ftp.set_pasv(True)
    return ftp


def _ftp_exists(ftp: Any, path: str) -> bool:
    import ftplib

    try:
        ftp.size(path)
    except ftplib.error_perm:
        return False
    except Exception:
        return False
    else:
        return True


def _ftp_makedirs(ftp: Any, path: str) -> None:
    """Create FTP directories recursively, ignoring already-exists errors."""
    import ftplib

    parts = [p for p in path.split("/") if p]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        with contextlib.suppress(ftplib.error_perm):  # already exists or permission
            ftp.mkd(current)


def _sync_ftp_upload(
    coordinator: BoschCameraCoordinator,
    data: dict[str, Any],
    token: str,
    prefetched_image: bytes | None = None,
) -> None:
    """Upload event files to an FTP server (e.g. FRITZ.NAS via plain FTP).

    ``prefetched_image`` — see ``sync_smb_upload`` docstring.
    """
    from io import BytesIO

    opts = coordinator.options
    server = opts.get("smb_server", "").strip()
    username = opts.get("smb_username", "").strip()
    password = opts.get("smb_password", "")
    base_path = opts.get("smb_base_path", "Bosch-Kameras").strip().strip("/")
    folder_pattern = opts.get("folder_pattern", "{camera}/{year}/{month}/{day}").strip()
    file_pattern = opts.get(
        "file_pattern", "{camera}_{date}_{time}_{type}_{id}"
    ).strip()

    if not server:
        return

    try:
        ftp = _ftp_connect(server, username, password)
    except Exception as err:
        _LOGGER.warning("FTP login to %s failed: %s", server, err)
        return

    try:
        for cam_id, cam_data in data.items():
            cam_name = _safe_name(cam_data["info"].get("title", cam_id))
            ev_list = cam_data.get("events", [])
            _LOGGER.debug("FTP upload: %s has %d events", cam_name, len(ev_list))

            for ev in ev_list:
                ts = ev.get("timestamp", "")
                if not ts or len(ts) < 19:
                    continue

                year = ts[:4]
                month = ts[5:7]
                day = ts[8:10]
                date_str = f"{year}-{month}-{day}"
                time_str = ts[11:19].replace(":", "-")
                etype = ev.get("eventType", "EVENT")
                ev_id = ev.get("id", "")[:8]

                folder_parts = folder_pattern.format(
                    year=year,
                    month=month,
                    day=day,
                    camera=cam_name,
                    type=etype,
                ).strip("/")
                file_base = file_pattern.format(
                    camera=cam_name,
                    date=date_str,
                    time=time_str,
                    type=etype,
                    id=ev_id,
                    year=year,
                    month=month,
                    day=day,
                )

                ftp_dir = f"/{base_path}/{folder_parts}".replace("//", "/").rstrip("/")
                _ftp_makedirs(ftp, ftp_dir)

                # Snapshot
                # Prefer prefetched_image bytes — see sync_smb_upload docstring.
                img_url = ev.get("imageUrl")
                _have_url = bool(img_url and _is_safe_bosch_url(img_url))
                if prefetched_image or _have_url:
                    fname = f"{file_base}.jpg"
                    fpath = f"{ftp_dir}/{fname}"
                    if _ftp_exists(ftp, fpath):
                        _LOGGER.debug("FTP skip (exists): %s", fname)
                    else:
                        try:
                            if prefetched_image:
                                content = prefetched_image
                                ftp.storbinary(f"STOR {fpath}", BytesIO(content))
                                _LOGGER.info(
                                    "FTP uploaded (prefetched): %s (%d bytes)",
                                    fname,
                                    len(content),
                                )
                            elif _have_url:
                                assert img_url is not None  # narrowed above
                                status, content = _http_get(img_url, token, timeout=30)
                                if status == 200 and content:
                                    ftp.storbinary(f"STOR {fpath}", BytesIO(content))
                                    _LOGGER.info(
                                        "FTP uploaded: %s (%d bytes)",
                                        fname,
                                        len(content),
                                    )
                                else:
                                    _LOGGER.warning(
                                        "FTP snapshot download failed: HTTP %d", status
                                    )
                        except Exception as err:
                            _LOGGER.warning("FTP upload error for %s: %s", fname, err)

                # Video clip
                clip_url = ev.get("videoClipUrl")
                clip_status = ev.get("videoClipUploadStatus", "")
                if clip_url and clip_status == "Done" and _is_safe_bosch_url(clip_url):
                    fname = f"{file_base}.mp4"
                    fpath = f"{ftp_dir}/{fname}"
                    if _ftp_exists(ftp, fpath):
                        _LOGGER.debug("FTP skip (exists): %s", fname)
                    else:
                        try:
                            req_obj = urllib.request.Request(  # Bosch cloud clip URL, https+bearer, guarded by _is_safe_bosch_url above
                                clip_url, headers={"Authorization": f"Bearer {token}"}
                            )
                            with (
                                urllib.request.urlopen(  # Bosch cloud clip URL, https+bearer, guarded by _is_safe_bosch_url above
                                    req_obj, context=_bosch_ssl_ctx(), timeout=60
                                ) as r
                            ):
                                if r.status == 200:
                                    ftp.storbinary(f"STOR {fpath}", r)
                                    _LOGGER.info("FTP uploaded: %s", fname)
                                else:
                                    _LOGGER.warning(
                                        "FTP clip download failed: HTTP %d", r.status
                                    )
                        except Exception as err:
                            _LOGGER.warning(
                                "FTP clip upload error for %s: %s", fname, err
                            )
    finally:
        try:
            ftp.quit()
        except Exception:
            with contextlib.suppress(Exception):
                ftp.close()


def _sync_ftp_cleanup(coordinator: BoschCameraCoordinator) -> None:
    """Delete files on the FTP server older than smb_retention_days."""
    from datetime import datetime
    import ftplib

    opts = coordinator.options
    server = opts.get("smb_server", "").strip()
    username = opts.get("smb_username", "").strip()
    password = opts.get("smb_password", "")
    base_path = opts.get("smb_base_path", "Bosch-Kameras").strip().strip("/")
    retention_days = int(opts.get("smb_retention_days", 180))

    if not opts.get("enable_smb_upload") or not server or retention_days <= 0:
        return

    try:
        ftp = _ftp_connect(server, username, password)
    except Exception as err:
        _LOGGER.warning("FTP cleanup: login to %s failed: %s", server, err)
        return

    cutoff = time.time() - retention_days * 86400
    deleted = 0

    def _walk_and_delete(path: str) -> None:
        nonlocal deleted
        try:
            ftp.cwd(path)
        except ftplib.error_perm:
            return
        entries: list[str] = []
        try:
            ftp.retrlines("LIST", entries.append)
        except Exception:
            return

        files: list[str] = []
        subdirs: list[str] = []
        for line in entries:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            perms, name = parts[0], parts[-1]
            if name in (".", ".."):
                continue
            if perms.startswith("d"):
                subdirs.append(name)
            elif perms.startswith("-"):
                files.append(name)

        for name in files:
            try:
                # MDTM for accurate mtime; falls back to LIST timestamp parsing if absent
                resp = ftp.sendcmd(f"MDTM {name}")
                # "213 YYYYMMDDHHMMSS"
                ts_str = resp.split()[-1]
                mt = (
                    datetime.strptime(ts_str[:14], "%Y%m%d%H%M%S")
                    .replace(tzinfo=UTC)
                    .timestamp()
                )
            except Exception:  # MDTM/parse failure → skip file, resilient cleanup loop
                continue
            if mt < cutoff:
                try:
                    ftp.delete(name)
                    deleted += 1
                except Exception as err:
                    _LOGGER.debug("FTP cleanup: delete %s failed: %s", name, err)

        for sub in subdirs:
            _walk_and_delete(f"{path}/{sub}")
            with contextlib.suppress(
                Exception
            ):  # sibling iteration proceeds regardless
                ftp.cwd(path)  # back up before next sibling

    try:
        root = f"/{base_path}"
        _walk_and_delete(root)
    finally:
        with contextlib.suppress(Exception):
            ftp.quit()

    if deleted:
        root_label = f"{server}/{base_path}"
        _LOGGER.info(
            "FTP cleanup: deleted %d file(s) older than %d days from %s",
            deleted,
            retention_days,
            root_label,
        )
        _fire_cleanup_alert(coordinator, deleted, retention_days, root_label)
