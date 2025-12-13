from __future__ import annotations

import ipaddress
import ssl
from functools import lru_cache
from pathlib import Path

from rebooterpro_async import RebooterProClient
from rebooterpro_async.client import DEFAULT_CA_BUNDLE

from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


async def async_get_client(hass, entry) -> RebooterProClient:
    """Return a shared client for this entry, creating it if needed."""
    store = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    if (client := store.get("client")) is None:
        session = async_get_clientsession(hass)
        ssl_ctx = await _get_ssl_for_host(hass, entry.data[CONF_HOST])
        # Pass pre-built SSL to avoid blocking load_verify_locations on the event loop.
        client = RebooterProClient(
            entry.data[CONF_HOST], session=session, ssl_context=ssl_ctx, ca_bundle=None
        )
        store["client"] = client
    return client


async def async_close_client(hass, entry_id: str) -> None:
    """Close and drop the shared client for an entry, if present."""
    client = hass.data.get(DOMAIN, {}).get(entry_id, {}).pop("client", None)
    if client:
        await client.aclose()


async def build_probe_client(hass, host: str) -> RebooterProClient:
    """Construct a transient client for probing a host during flows."""
    session = async_get_clientsession(hass)
    ca_bundle = await _get_ca_bundle_offthread(hass)
    # Avoid blocking the event loop when loading the embedded CA; build the client in an executor.
    return await hass.async_add_executor_job(
        lambda: RebooterProClient(host, session=session, ca_bundle=ca_bundle)
    )


@lru_cache(maxsize=1)
def _cached_ca_path() -> Path | None:
    from importlib.resources import files

    try:
        path = files("rebooterpro_async.data") / "device_ca.pem"
        return path if path.exists() else None
    except Exception:
        return None


async def _get_ca_bundle_offthread(hass) -> Path | None:
    """Load the embedded CA path off the event loop."""
    return await hass.async_add_executor_job(_cached_ca_path)


def _build_ctx_from_ca(ca_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    ctx.load_verify_locations(cafile=str(ca_path))
    return ctx


async def _get_ssl_for_host(hass, host: str) -> ssl.SSLContext | bool | None:
    """Return ssl= value for aiohttp built off-thread to avoid loop blocking."""
    host = (host or "").strip()
    try:
        if host:
            ipaddress.ip_address(host)
            return False
    except ValueError:
        pass

    if DEFAULT_CA_BUNDLE and DEFAULT_CA_BUNDLE.exists():
        return await hass.async_add_executor_job(_build_ctx_from_ca, DEFAULT_CA_BUNDLE)

    return None
