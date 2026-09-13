"""Config flow for Habitron integration."""

import contextlib
import logging
import socket
from typing import Any, override
from urllib.parse import urlparse

from habitron_client import (
    HabitronClient,
    HabitronConnectionError,
    HabitronError,
    discover_smarthubs,
    get_host_ip,
    test_connection,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import network
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_DEFAULT_HOST, DOMAIN, normalised_mac

_LOGGER = logging.getLogger(__name__)


async def _async_hub_mac(host: str) -> str | None:
    """Return the hub's MAC, or ``None`` when it reports none.

    This is the identity every path keys on: it is the same whichever interface
    the hub currently uses, and the custom (HACS) integration derives it the
    same way, so an installation moving to core is recognised rather than
    offered a second time.

    A hub that cannot be reached raises ``CannotConnect`` instead of returning
    ``None``: the two need different answers -- "update the hub software" helps
    nobody whose address is simply wrong.
    """
    try:
        async with HabitronClient(host) as client:
            info = await client.get_smhub_info()
    except (HabitronError, OSError) as err:
        raise CannotConnect from err
    try:
        # A hub without an Ethernet interface reports the key as null, and
        # ``str(None)`` would normalise to the literal "none" -- an id every
        # such hub would share. Treat it as absent, like a missing key.
        reported = str(info["hardware"]["network"]["lan mac"] or "")
    except (KeyError, TypeError) as err:
        _LOGGER.debug("Hub at %s reported no readable MAC: %s", host, err)
        return None
    if (mac := normalised_mac(reported)) is None:
        _LOGGER.debug("Hub at %s reported %r, which is no MAC", host, reported)
    return mac


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    host_input = data[CONF_HOST]

    # The hub runs on this machine when the entered address is *any* of HA's own
    # local addresses -- not just the route-selected one. A multi-homed host, or
    # a SmartCenter reachable over both LAN and WLAN, has several; match them all
    # so the same hub is not stored once as a remote address and once as
    # ``local``. Typing ``local`` explicitly still works (it is not an IP, so it
    # falls through to the sentinel branch below).
    own_ips = {str(ip) for ip in await network.async_get_enabled_source_ips(hass)}
    if host_input in own_ips:
        host_input = CONF_DEFAULT_HOST
        data[CONF_HOST] = CONF_DEFAULT_HOST

    host_to_test = host_input
    if host_to_test == CONF_DEFAULT_HOST:
        # Resolve the sentinel to a concrete local IP for the probe.
        host_to_test = await network.async_get_source_ip(hass)

    # Resolve the name first so an unresolvable host maps to ``host_not_found``
    # ("try an IP") rather than a generic connection error. ``get_host_ip``
    # raises ``HabitronConnectionError`` only for a DNS failure; ``test_connection``
    # resolves internally too and wraps *every* failure (DNS included) into a
    # ``HabitronError``, so without resolving here a bad name would only ever
    # surface as ``cannot_connect``.
    try:
        await get_host_ip(host_to_test)
    except HabitronConnectionError as exc:
        raise HostNotFound from exc

    # Connection test. ``test_connection`` wraps expected connection failures
    # into ``HabitronError``; anything else (e.g. a response-processing bug)
    # propagates so the caller's ``unknown`` path surfaces the real fault
    # instead of hiding it as a network error.
    try:
        result, host_name = await test_connection(host_to_test)
    except (OSError, TimeoutError, HabitronError) as exc:
        raise CannotConnect from exc

    if not result:
        raise CannotConnect

    # ``test_connection`` returns an empty name when the TCP probe succeeds but
    # the hub's metadata query gets no answer. Fall back to the probed address
    # (the resolved own IP for the ``local`` sentinel) so the entry never ends
    # up with a blank title.
    return {"title": host_name or host_to_test}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitron."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: dict[str, Any] = {}
        self._udp_devices: list[dict[str, str]] | None = None

    async def _cached_discover(self) -> list[dict[str, str]]:
        """Run the network discovery once per flow and reuse the result.

        The scan blocks briefly; the user step would otherwise run it both when
        showing the form and again on submit. A discovery failure yields an
        empty list so the flow still offers the manual host entry.
        """
        if self._udp_devices is None:
            try:
                self._udp_devices = await discover_smarthubs()
            except (HabitronError, OSError) as err:
                # A missing route/interface surfaces as OSError from the own-IP
                # lookup; either way discovery is best-effort, so fall back to
                # the empty list and let the user enter the host manually.
                _LOGGER.debug("SmartHub discovery failed: %s", err)
                self._udp_devices = []
        return self._udp_devices

    async def _async_canonical_host(self, host: str) -> str:
        """Return a comparable form of ``host``.

        The same hub can be entered in more than one way, and comparing the raw
        strings would miss that, adding a second entry -- and a second
        connection -- to a hub that is already configured. Canonicalised here:
        the ``local`` sentinel (a hub on Home Assistant's own machine, stored as
        the sentinel rather than as that IP) and casing, which is insignificant
        for host names.

        Both the manual and the SSDP step compare through this, so the same hub
        is recognised whichever way it was first added.
        """
        # Any of HA's own local addresses is the same machine as the ``local``
        # sentinel: a multi-homed host, or a SmartCenter reachable over both LAN
        # and WLAN, exposes several. Collapse them all to the sentinel so an
        # entry stored under one local address still matches another.
        own_ips = {
            str(ip) for ip in await network.async_get_enabled_source_ips(self.hass)
        }
        if host == CONF_DEFAULT_HOST or host in own_ips:
            return CONF_DEFAULT_HOST
        with contextlib.suppress(OSError):
            resolved = await self.hass.async_add_executor_job(
                socket.gethostbyname, host
            )
            # A name that resolves to one of our own addresses is the same
            # machine as the sentinel; returning the bare IP here would make
            # ``smarthub.local`` and an entry stored as ``local`` look different.
            if resolved in own_ips:
                return CONF_DEFAULT_HOST
            return resolved
        return host.casefold()

    async def _async_stored_host(self, host: str) -> str:
        """Return ``host`` in the form an entry stores it.

        ``validate_input`` writes any of Home Assistant's own addresses as the
        ``local`` sentinel, so anything that derives an id from -- or writes --
        the stored host has to use the same form.
        """
        own_ips = {
            str(ip) for ip in await network.async_get_enabled_source_ips(self.hass)
        }
        return CONF_DEFAULT_HOST if host in own_ips else host

    async def _async_probe_host(self, host: str) -> str:
        """Return an address the hub client can actually dial.

        ``local`` is our own sentinel, not a name any resolver knows, and the
        UDP probe answers with the address it was reached at -- so a name is
        resolved too, or its reply cannot be matched.
        """
        if host == CONF_DEFAULT_HOST:
            return await network.async_get_source_ip(self.hass)
        with contextlib.suppress(OSError):
            return await self.hass.async_add_executor_job(socket.gethostbyname, host)
        return host

    async def _async_hub_identity(self, host: str) -> str | None:
        """Return the id this hub is keyed by: its MAC, or ``None``.

        The MAC is the only identity, on every path. It is the one identifier
        both the manual and the discovery flow can obtain, it survives every
        address change, and the custom (HACS) integration derives it the same
        way -- so an installation moving over is recognised instead of being
        offered a second time. There is no fallback: a hub that answers but
        reports no usable ``lan mac`` yields ``None``, and both callers refuse
        it rather than invent an id two hubs could share. A hub that cannot be
        reached raises ``CannotConnect``, which is a different answer for the
        user (see ``_async_hub_mac``).
        """
        return await _async_hub_mac(await self._async_probe_host(host))

    async def _async_matching_entry(
        self,
        entries: list[config_entries.ConfigEntry],
        *hosts: str | None,
    ) -> config_entries.ConfigEntry | None:
        """Return the entry already configured for one of ``hosts``, if any.

        Both sides have to be canonicalised: an entry added manually as
        ``smarthub.local`` and a discovery reporting ``192.168.1.50`` are the
        same hub, and comparing the raw strings would miss that and offer a
        duplicate entry -- and a second connection -- for a hub that is
        already configured.
        """
        candidates = {host for host in hosts if host}
        # Nothing configured (or nothing to compare): skip the canonicalisation
        # and its name lookups, there is nothing this could collide with.
        if not entries or not candidates:
            return None
        canonical = {await self._async_canonical_host(host) for host in candidates}
        for entry in entries:
            entry_host = entry.data.get(CONF_HOST)
            if not entry_host:
                continue
            if entry_host in candidates:
                return entry
            if await self._async_canonical_host(entry_host) in canonical:
                return entry
        return None

    async def _is_device_already_configured(
        self, host: str, ip: str | None = None
    ) -> bool:
        """Check if a device with this host or IP is already configured.

        ``_async_current_entries`` skips ignored entries in a user flow, which
        is what makes an ignored hub configurable again by hand: core lets
        ``_abort_if_unique_id_configured`` through for that case, so this check
        must not abort behind its back.
        """
        return (
            await self._async_matching_entry(
                list(self._async_current_entries()), host, ip
            )
            is not None
        )

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle SSDP discovery."""
        host = (
            urlparse(discovery_info.ssdp_location).hostname
            if discovery_info.ssdp_location
            else None
        )
        if not host:
            return self.async_abort(reason="no_host_in_ssdp")
        host_str = str(host)

        # No UDP scan here: the only field taken from it was the address, and
        # that is ``host_str`` by construction -- scanning would just delay the
        # flow.
        self._discovered_device = {"ip": host_str}

        try:
            unique_id = await self._async_hub_identity(host_str)
        except CannotConnect:
            # Advertised but not reachable right now. Dropping the flow is the
            # honest answer: SSDP re-announces, so it comes back on its own.
            return self.async_abort(reason="cannot_connect")
        if unique_id is None:
            # No MAC, no identity: a hub that cannot be told apart from another
            # must not be offered, or two of them would share an entry.
            return self.async_abort(reason="no_mac_address")

        await self.async_set_unique_id(unique_id)
        # The entry registers an update listener that reloads on a data change,
        # so leave the reload to it: having both schedules two reloads and is
        # reported as breaking in 2026.12. The host is written in stored form --
        # overwriting a ``local`` entry with the discovered IP would leave setup
        # pointing at a stale address once that IP changes.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: await self._async_stored_host(host_str)},
            reload_on_update=False,
        )

        self.context["title_placeholders"] = {"name": host_str}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Create entry with discovered data
            data = {CONF_HOST: self._discovered_device.get("ip")}
            try:
                info = await validate_input(self.hass, data)
                return self.async_create_entry(title=info["title"], data=data)
            except CannotConnect, HostNotFound:
                # A briefly-offline hub or an unresolved discovery host should be
                # retryable via the confirmation form, not aborted.
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovered_device.get("ip", "Habitron Hub")
            },
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        default_host = CONF_DEFAULT_HOST

        # Pre-fill with discovery if just opened
        if user_input is None:
            discovered = await self._cached_discover()

            # Filter: Keep only devices that are NOT yet configured
            valid_devices = [
                d
                for d in discovered
                if not await self._is_device_already_configured(d.get("ip", ""))
            ]
            if valid_devices:
                default_host = valid_devices[0].get("ip", CONF_DEFAULT_HOST)

        if user_input is not None:
            host_input = user_input[CONF_HOST]

            # Reachability first: it separates a wrong address from a hub that
            # answers but reports no MAC, and it is what tells an unresolvable
            # name ("try an IP") from a refused connection. Asking for the
            # identity first would report every one of them as a missing MAC.
            try:
                info = await validate_input(self.hass, user_input)
                unique_id = await self._async_hub_identity(host_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HostNotFound:
                errors["base"] = "host_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if unique_id is None:
                    # The hub answers but has no MAC, so it cannot be told apart
                    # from another one. Shown on the form rather than aborted:
                    # updating the hub's software makes the retry work.
                    errors["base"] = "no_mac_address"
                else:
                    await self.async_set_unique_id(unique_id)
                    # Re-entering a known hub at a new address updates the
                    # stored host, so a DHCP change does not leave the entry on
                    # the old one. The entry's update listener handles the
                    # reload. An ignored entry is deliberately let through:
                    # adding it by hand is how un-ignoring works, and the new
                    # entry replaces it.
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: await self._async_stored_host(host_input)},
                        reload_on_update=False,
                    )
                    return self.async_create_entry(title=info["title"], data=user_input)

            default_host = user_input[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default_host): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class HostNotFound(exceptions.HomeAssistantError):
    """Error to indicate DNS name is not found."""
