from __future__ import annotations

import logging
import re
import ipaddress
from typing import Any
import voluptuous as vol

import socket
import asyncio

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .ssl_utils import get_aiohttp_ssl

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Only hostname is requested now
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="rebooter-pro.local"): str,
})


def _zget(obj: Any, attr: str, default: Any = None) -> Any:
    """Get zeroconf info attribute from either ZeroconfServiceInfo or a dict."""
    if hasattr(obj, attr):
        try:
            return getattr(obj, attr)
        except Exception:
            pass
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default

DEVICE_PREFIX = "CS-RBTR-"
_SERIAL_RE = re.compile(r"^(\d+)$") #for https poll of serial
_NAME_SERIAL_RE = re.compile(r"Rebooter Pro\s+(\d+)", re.IGNORECASE) #for dns name
async def _probe_serial_over_https(hass, entry_or_host) -> str | None:
    """Return the numeric serial from GET /info (device), or None on failure.

    Accepts either a ConfigEntry or a host string for convenience.
    """
    # Normalize inputs
    if isinstance(entry_or_host, str):
        entry = None
        host = (entry_or_host or "").strip()
    else:
        entry = entry_or_host
        host = (entry.data.get(CONF_HOST) or "").strip() if entry else ""

    if not host:
        return None

    base = f"https://{host}:443"
    session = async_get_clientsession(hass)

    # SSL context selection:
    # - If we have a ConfigEntry, use your existing helper (unchanged).
    # - If we only have a host string:
    #     * IP -> disable verification (False)
    #     * hostname -> use default verification (None)
    if entry is not None:
        ssl_ctx = await get_aiohttp_ssl(hass, entry)
    else:
        try:
            ipaddress.ip_address(host)
            ssl_ctx = False  # IP: skip hostname verification
        except ValueError:
            ssl_ctx = False

    try:
        async with session.get(f"{base}/info", ssl=ssl_ctx, timeout=8) as r:
            if r.status != 200:
                _LOGGER.debug("GET /info on %s returned %s", host, r.status)
                return None
            data = await r.json(content_type=None)
    except Exception as exc:
        _LOGGER.debug("GET /info failed for %s: %r", host, exc)
        return None

    device_field = (data or {}).get("device")
    if not isinstance(device_field, str):
        return None

    # Strip the leading "CS-RBTR-" if present
    if device_field.startswith(DEVICE_PREFIX):
        candidate = device_field[len(DEVICE_PREFIX):]
    else:
        candidate = device_field

    candidate = candidate.strip()
    # Prefer returning a pure numeric serial; otherwise fall back to the cleaned string
    if _SERIAL_RE.match(candidate):
        return candidate

    _LOGGER.debug("Unexpected device format in /info: %r", device_field)
    return candidate or None

# --- mDNS helper: map an IP -> .local hostname by browsing services briefly ---
async def _mdns_hostname_for_ip(hass, ip: str, timeout: float = 2.0) -> str | None:
    """Return 'host.local' for a device advertising on mDNS at the given IP, else None."""
    from homeassistant.components.zeroconf import async_get_instance
    from zeroconf import ServiceBrowser, Zeroconf

    SERVICE_TYPES = [
        "_https._tcp.local.",
        "_http._tcp.local.",
        # e.g. "_rebooter-pro._tcp.local.",
    ]

    zc: Zeroconf = await async_get_instance(hass)
    result: dict[str, str | None] = {"host": None}

    def _search() -> str | None:
        import time
        import socket

        class _Listener:
            def add_service(self, zc: Zeroconf, stype: str, name: str) -> None:
                info = zc.get_service_info(stype, name, timeout=200)
                if not info:
                    return
                addrs = []
                # Zeroconf returns packed bytes; convert to dotted-quad (IPv4 only)
                for a in (info.addresses or []):
                    try:
                        addrs.append(socket.inet_ntoa(a))
                    except Exception:
                        pass
                if ip in addrs:
                    host = (info.server or "").rstrip(".").lower()
                    if host:
                        result["host"] = host

            # Keep zeroconf happy on newer versions
            def update_service(self, zc: Zeroconf, stype: str, name: str) -> None:
                return

            def remove_service(self, zc: Zeroconf, stype: str, name: str) -> None:
                return

        browsers: list[ServiceBrowser] = []
        try:
            for st in SERVICE_TYPES:
                browsers.append(ServiceBrowser(zc, st, _Listener()))
            # Wait up to `timeout` seconds for a match
            end = time.monotonic() + timeout
            while time.monotonic() < end and result["host"] is None:
                time.sleep(0.05)
        finally:
            # Actively stop the browsers; do NOT close `zc` (managed by HA)
            for b in browsers:
                try:
                    b.cancel()
                except Exception:
                    pass

        return result["host"]

    try:
        return await hass.async_add_executor_job(_search)
    except Exception:
        return None



def _norm_host(s: str | None) -> str:
    s = (s or "").strip()
    if s.endswith("."):
        s = s[:-1]
    return s.lower()

class RebooterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    def __init__(self) -> None:
        self._discovered: dict[str, str] | None = None
        self._zc: dict[str, str] = {}  # holds zeroconf details for confirm step

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)
    
        host = _norm_host(user_input.get(CONF_HOST))
        
        # Guard against empty/invalid host field
        if not host:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors={"base": "cannot_connect"})
    
        # If the user typed an IP, try reverse DNS to prefer a hostname
        preferred_host = host
        is_ip = False
        try:
            ipaddress.ip_address(host)
            is_ip = True
            _LOGGER.debug("User entered IP '%s'; downstream SSL helper should disable hostname verification.", host)
        except ValueError:
            pass
    
        if is_ip:
            # Prefer a true mDNS hostname (e.g. rebooter-pro-2.local) over the IP
            mdns_host = await _mdns_hostname_for_ip(self.hass, host, timeout=2.0)
            if mdns_host:
                _LOGGER.debug("mDNS lookup for %s -> adopting hostname '%s'", host, mdns_host)
                preferred_host = mdns_host
            else:
                _LOGGER.debug("mDNS lookup for %s found no hostname; keeping IP", host)


        # Try to fetch a stable serial now so manual setup and Zeroconf share the same unique_id
        try:
            serial = await _probe_serial_over_https(self.hass, preferred_host)
        except Exception as e:
            _LOGGER.debug("Serial probe failed for %s: %r", preferred_host, e)
            serial = None
            
        # If the probe failed (unreachable or invalid /info), do NOT add the entry.
        if not serial:
            _LOGGER.debug("Host '%s' unreachable or /info invalid; not creating entry.", preferred_host)
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
            )
    
        _LOGGER.debug("Integration using unique id '%s'", serial)

        self.context["title_placeholders"] = {
            "serial": str(serial),
            "host": preferred_host,
        }
        
        await self.async_set_unique_id(str(serial), raise_on_progress=False)
        self._abort_if_unique_id_configured(updates={CONF_HOST: preferred_host})
        
        # Use a serial-based title
        title = f"Rebooter Pro {serial}"
        return self.async_create_entry(
            title=title,
            data={CONF_HOST: preferred_host},
        )


    async def async_step_zeroconf(self, discovery_info: Any):
        # Handle both ZeroconfServiceInfo and dict payloads
        hostname_raw = _zget(discovery_info, "hostname") or ""
        hostname = _norm_host(hostname_raw)

        ips = _zget(discovery_info, "ip_addresses") or []
        if not ips:
            single_ip = _zget(discovery_info, "ip_address")
            if single_ip:
                ips = [single_ip]

        host_attr = _zget(discovery_info, "host")

        # Prefer mDNS hostname; otherwise fall back to an IP
        if hostname:
            host = hostname
        else:
            host = _norm_host(host_attr or (ips[0] if ips else None))
            _LOGGER.debug(
                "Zeroconf fallback to IP '%s'; downstream SSL helper should disable hostname verification.",
                host,
            )

        name = _zget(discovery_info, "name") or ""  # e.g. "Rebooter Pro 1010001._https._tcp.local."
        m = _NAME_SERIAL_RE.search(name)
        serial = m.group(1) if m else None

        # If the serial isn’t in the service name, probe over HTTPS /info (returns a serial string or None)
        if not serial and host:
            try:
                serial = await _probe_serial_over_https(self.hass, host)
            except Exception as e:
                _LOGGER.debug("Zeroconf: probe /info failed for %s: %r", host, e)

        # Final fallback if we still couldn't determine a serial
        if not serial:
            serial = hostname or host or "rebooter-pro"

        _LOGGER.debug(
            "Integration using unique id '%s'",
            str(serial),
        )

        # Use serial as the unique id so IP/hostname changes won’t duplicate entries
        await self.async_set_unique_id(str(serial), raise_on_progress=False)
        # If it already exists, update host and abort (normal dedupe behavior)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Stash details for the dedicated confirm step
        self._zc = {"host": host, "serial": str(serial), "model": "Rebooter Pro"}
        self.context.update({
            "title_placeholders": {
                "serial": self._zc["serial"],
                "model": self._zc["model"],
            }
        })
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle the user clicking Configure on the discovery tile."""
        if not self._zc:
            return self.async_abort(reason="unknown")
        host = self._zc["host"]
        serial = self._zc["serial"]

        if user_input is not None:
            title = f"{self._zc['model']} {serial}"
            return self.async_create_entry(title=title, data={CONF_HOST: host, **user_input})

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "serial": serial,
                "model": self._zc["model"],
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        from .options_flow import RebooterOptionsFlowHandler
        return RebooterOptionsFlowHandler(config_entry)
