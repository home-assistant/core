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
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import CONF_DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalised_mac(value: str) -> str:
    """Return a MAC comparable across separators and casing."""
    return value.replace(":", "").replace("-", "").casefold()


async def _async_hub_mac(host: str) -> str | None:
    """Return the hub's MAC, or ``None`` when it cannot be read.

    Only used to recognise an entry that was created by the custom (HACS)
    integration, which keys its entries by the hub's colon-stripped MAC -- an
    id this flow never produces itself.
    """
    try:
        async with HabitronClient(host) as client:
            info = await client.get_smhub_info()
        mac = str(info["hardware"]["network"]["lan mac"])
    except (HabitronError, OSError, KeyError, TypeError) as err:
        _LOGGER.debug("Could not read the MAC from the hub at %s: %s", host, err)
        return None
    return _normalised_mac(mac) or None


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
        host_input = "local"
        data[CONF_HOST] = "local"

    host_to_test = host_input
    if host_to_test == "local":
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

        ``local`` is our own sentinel, not a name any resolver knows -- unlike
        ``HbtnComm``, the direct client calls here would just fail on it, and
        with them the stable-id fallback and the legacy-MAC lookup.
        """
        if host == CONF_DEFAULT_HOST:
            return await network.async_get_source_ip(self.hass)
        return host

    async def _async_resolved_host(self, host: str) -> str:
        """Return ``host`` as an address, or unchanged when it does not resolve.

        Unlike ``_async_canonical_host`` this keeps a local address as-is: the
        UDP probe reports the address it answered at, so a hub on this machine
        has to be matched by that address, not by the ``local`` sentinel -- the
        sentinel is mapped to that address first, since no resolver knows it.
        """
        host = await self._async_probe_host(host)
        with contextlib.suppress(OSError):
            return await self.hass.async_add_executor_job(socket.gethostbyname, host)
        return host

    async def _async_mac_matching_entry(
        self, host: str
    ) -> config_entries.ConfigEntry | None:
        """Return an entry keyed by this hub's MAC, if there is one.

        Entries created by the custom (HACS) integration use the hub's MAC as
        their unique id, which this flow never derives -- it keys on the UPnP
        serial, the UDN or the host. Without this the same hub is offered as a
        new device once its address changes, because neither the unique id nor
        the stored host matches any more. Probing costs one request, so it runs
        only after the cheaper checks came up empty.
        """
        macs = {
            _normalised_mac(entry.unique_id): entry
            for entry in self._async_current_entries(include_ignore=True)
            if entry.unique_id
        }
        if not macs:
            return None
        hub_mac = await _async_hub_mac(await self._async_probe_host(host))
        return macs.get(hub_mac) if hub_mac else None

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

        # Prefer stable identifiers from the UPnP description; fall back
        # to a discovery probe (which may return a serial), and only use the
        # host as last resort. A host-based id changes on DHCP-lease
        # renewals and would otherwise look like a new device.
        upnp = discovery_info.upnp or {}
        unique_id: str | None = upnp.get(ATTR_UPNP_SERIAL)
        target_device: dict[str, str] | None = None

        if not unique_id:
            # Ask the UDP probe for a serial before considering the UDN. The
            # manual path keys on that serial, and two paths keying the same hub
            # differently is exactly what lets it be added a second time once
            # its address changes: neither the ids nor the stored hosts match
            # then.
            devices = await self._cached_discover()
            target_device = next((d for d in devices if d.get("ip") == host_str), None)
            if target_device:
                unique_id = target_device.get("serial") or None
        if not unique_id:
            unique_id = upnp.get(ATTR_UPNP_UDN)

        self._discovered_device = target_device or {"ip": host_str}

        if not unique_id:
            # No stable id advertised: the MAC still identifies the hub across
            # address changes, the host does not.
            unique_id = await _async_hub_mac(host_str)
        if not unique_id:
            _LOGGER.warning(
                "Habitron at %s exposed no UDN/serial/MAC; using host as fallback id",
                host_str,
            )
            unique_id = f"habitron_{host_str}"

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

        # The unique_id did not match an existing entry. The same SmartHub
        # may already be configured under a host-based fallback id — the
        # manual step falls back to ``habitron_<host>`` when no serial is
        # available, while SSDP yields a stable UDN/serial. Match on the
        # host/IP so we adopt the stable id and abort instead of offering a
        # duplicate of the hub the user already added.
        # ``_async_matching_entry`` canonicalises both sides, so this also
        # matches an entry stored under a host name (or under the ``local``
        # sentinel, which resolves to Home Assistant's own address) against the
        # IP the discovery reports.
        if entry := await self._async_matching_entry(
            # Ignored entries count: a host-fallback entry the user ignored must
            # not be offered again just because this discovery has a stable UDN.
            list(self._async_current_entries(include_ignore=True)),
            host_str,
            self._discovered_device.get("ip"),
        ):
            # Adopt the discovered id only over a host-based fallback, and only
            # when this run produced a stable one. Rewriting an existing stable
            # id would flip a serial-keyed entry to a UDN whenever a discovery
            # omits the serial -- and back again when it returns; keeping the
            # fallback would leave the entry unmatched after a DHCP change,
            # letting the same hub be offered as a duplicate.
            fallback_id = f"habitron_{host_str}"
            if unique_id != fallback_id and str(entry.unique_id).startswith(
                "habitron_"
            ):
                self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
            return self.async_abort(reason="already_configured")

        # Last resort: an entry the custom integration created keys on the hub's
        # MAC, so neither the id nor -- after an address change -- the host
        # matches. Adopt the discovered id, which this flow can derive again.
        if entry := await self._async_mac_matching_entry(host_str):
            self.hass.config_entries.async_update_entry(
                entry,
                unique_id=unique_id,
                data={**entry.data, CONF_HOST: await self._async_stored_host(host_str)},
            )
            return self.async_abort(reason="already_configured")

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
            # Try a discovery probe to obtain a stable serial-based unique_id;
            # fall back to the host string when no probe response arrives.
            host_input = user_input[CONF_HOST]
            # The probe reports the address it was reached at, so match it
            # against what the user submitted -- canonicalising first would
            # discard the serial of a hub running on this machine.
            unique_id: str | None = None
            devices = await self._cached_discover()
            # The probe answers with an address, so a submitted host name has to
            # be resolved before comparing -- otherwise its serial is dropped and
            # the hub gets a host-based id that a later address change breaks.
            probe_hosts = {host_input, await self._async_resolved_host(host_input)}
            target = next((d for d in devices if d.get("ip") in probe_hosts), None)
            if target:
                # An empty serial is no identifier: it would collide with every
                # other hub that reports a blank one.
                unique_id = target.get("serial") or None
            stored_host = await self._async_stored_host(host_input)
            if unique_id is None:
                # The MAC identifies the hub across address changes; a
                # host-based id would produce a second entry for the same hub
                # after every DHCP lease change.
                unique_id = await _async_hub_mac(
                    await self._async_probe_host(host_input)
                )
            if unique_id is None:
                unique_id = f"habitron_{stored_host}"

            await self.async_set_unique_id(unique_id)
            # Re-entering a known hub at a new address updates the stored host,
            # so a DHCP change does not leave the entry on the old one. The
            # entry's update listener handles the reload.
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: stored_host}, reload_on_update=False
            )

            # A hub already added via SSDP is keyed by its UDN, so the serial-
            # or host-based unique_id derived here does not match it. Guard
            # against a duplicate entry (and a second connection to the same
            # hub) by also checking the entered host/IP against existing entries.
            probed_ip = target.get("ip") if target else None
            # Use the canonicalized host: an own-IP entry is stored as ``local``,
            # so an SSDP entry that was likewise canonicalized is only matched
            # when we compare against ``host_input`` rather than the raw input.
            if await self._is_device_already_configured(host_input, probed_ip):
                return self.async_abort(reason="already_configured")

            # An entry from the custom integration is keyed by the hub's MAC;
            # re-adding the same hub at a new address would otherwise duplicate
            # it, since neither its id nor its stored host still matches.
            if entry := await self._async_mac_matching_entry(host_input):
                if entry.source == config_entries.SOURCE_IGNORE:
                    # Adding an ignored hub by hand is how un-ignoring works --
                    # core lets the new entry replace the ignored one. Adopt its
                    # MAC as our id so the replacement is recognised, and carry
                    # on to create the entry instead of aborting.
                    await self.async_set_unique_id(entry.unique_id)
                else:
                    # Only the address needs correcting: the entry is already
                    # keyed by the MAC, the most stable id available here --
                    # replacing it with a host-based fallback would undo that.
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_HOST: stored_host}
                    )
                    return self.async_abort(reason="already_configured")

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HostNotFound:
                errors["base"] = "host_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

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
