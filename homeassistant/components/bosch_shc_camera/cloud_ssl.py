"""Centralised TLS trust for Bosch public cloud and OAuth endpoints.

Bosch's residential cloud API (``residential.cbs.boschsecurity.com``) and the
live video proxy (``proxy-*.cbs.boschsecurity.com``) are served by a *private*
Bosch PKI (``Bosch ST Root CA`` -> ``Video CA 2A``) that is not present in any
public trust store, so the system default verification rejects them. The
OAuth / Keycloak host (``smarthome.authz.bosch.com``) uses a public Let's
Encrypt certificate.

Historically every outbound call to those hosts used ``verify_ssl=False`` /
``ssl=False`` (GHSA-6qh5-x5m5-vj6v, CWE-295), which accepted *any* certificate
and let an adjacent-network attacker MITM the OAuth tokens and cloud traffic.

This module builds a single SSL context that trusts BOTH the system roots (for
the Let's Encrypt OAuth host and any other public host) AND the Bosch private
CA (for the cloud REST API and the video proxy). It rejects self-signed and
otherwise untrusted certificates, closing the MITM hole while keeping every
Bosch cloud call working.

Local camera endpoints (LAN IPs) use per-device self-signed certificates and
intentionally keep ``verify_ssl=False`` -- that is a documented local-network
exception and is out of scope for this module.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import ssl
from typing import Any, cast

import aiohttp

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

# Bosch "Video CA 2A" intermediate CA, issued by the private "Bosch ST Root CA".
# Extracted from the live residential.cbs.boschsecurity.com certificate chain.
# Validity: 2021-03-18 .. 2057-03-20.
# SHA-256 fingerprint:
#   9F:6A:CB:6D:79:38:60:A3:B1:B4:37:EA:D3:A7:D5:A6:
#   28:D0:28:8E:24:41:52:A5:E9:C9:6B:36:51:D6:01:D1
BOSCH_CLOUD_CA_PEM = """\
-----BEGIN CERTIFICATE-----
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
nvQ8Em1LhUA=
-----END CERTIFICATE-----
"""

_SSL_CONTEXT: ssl.SSLContext | None = None
_SSL_CONTEXT_LOCK: asyncio.Lock | None = None
_SESSION_DATA_KEY = "bosch_shc_camera_cloud_session"
_SESSION_LOCK: asyncio.Lock | None = None


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context trusting system roots plus the Bosch private CA.

    Performs blocking I/O (loads the system CA bundle), so it must be called
    from an executor thread, never directly on the event loop.
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=BOSCH_CLOUD_CA_PEM)
    # The pinned Bosch CA is an intermediate (not a self-signed root), so allow
    # OpenSSL to anchor the chain at it. This does not weaken validation of
    # public hosts: their chains still terminate at a trusted system root.
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


async def async_get_bosch_cloud_ssl_context(hass: HomeAssistant) -> ssl.SSLContext:
    """Return a cached SSL context for Bosch public cloud / OAuth hosts."""
    global _SSL_CONTEXT, _SSL_CONTEXT_LOCK
    if _SSL_CONTEXT is not None:
        return _SSL_CONTEXT
    # Lazily create the lock on first call (must be on the event loop)
    if _SSL_CONTEXT_LOCK is None:
        _SSL_CONTEXT_LOCK = asyncio.Lock()
    async with _SSL_CONTEXT_LOCK:
        # Double-check inside the lock (another coroutine may have built it)
        if _SSL_CONTEXT is None:
            _SSL_CONTEXT = await hass.async_add_executor_job(_build_ssl_context)
    return _SSL_CONTEXT


async def async_get_bosch_cloud_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Return a cached aiohttp session that verifies Bosch cloud TLS.

    Used for every Bosch internet-facing endpoint: the cloud REST API, the
    OAuth / Keycloak token exchange, and the live video proxy. Replaces the
    previous ``verify_ssl=False`` sessions that accepted any certificate
    (GHSA-6qh5-x5m5-vj6v / CWE-295).
    """
    global _SESSION_LOCK
    existing = cast("aiohttp.ClientSession | None", hass.data.get(_SESSION_DATA_KEY))
    if existing is not None and not existing.closed:
        return existing

    # Lazily create the lock on first call (must be on the event loop).
    if _SESSION_LOCK is None:
        _SESSION_LOCK = asyncio.Lock()
    async with _SESSION_LOCK:
        # Double-check inside the lock: another coroutine may have already
        # built and stored the session while we awaited the lock (HA starts
        # camera/switch/light/sensor platforms concurrently at integration
        # setup, so this is a realistic race, not just theoretical).
        existing = cast(
            "aiohttp.ClientSession | None", hass.data.get(_SESSION_DATA_KEY)
        )
        if existing is not None and not existing.closed:
            return existing

        ssl_context = await async_get_bosch_cloud_ssl_context(hass)
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        session = aiohttp.ClientSession(connector=connector)
        hass.data[_SESSION_DATA_KEY] = session

        async def _close_session(_event: Any) -> None:
            if not session.closed:
                await session.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close_session)
        return session


@asynccontextmanager
async def async_bosch_cloud_session_cm(
    hass: HomeAssistant,
) -> AsyncIterator[aiohttp.ClientSession]:
    """Yield the shared Bosch cloud session as an async CM that does NOT close it.

    The session from :func:`async_get_bosch_cloud_session` is process-wide and
    closed once on ``EVENT_HOMEASSISTANT_STOP``. Hot paths that used to do
    ``async with aiohttp.ClientSession(connector=TCPConnector(ssl=...)) as
    session:`` — opening a fresh TCP+TLS connection on every poll/heartbeat —
    switch to ``async with async_bosch_cloud_session_cm(hass) as session:`` with
    a one-line change (no large de-indent) and gain connection pooling. Per the
    aiohttp docs a single application-lifetime session is the recommended
    pattern; per-request sessions defeat pooling and add handshake latency.
    """
    yield await async_get_bosch_cloud_session(hass)
