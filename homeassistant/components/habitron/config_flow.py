"""Config flow for Habitron integration."""

import contextlib
import logging
import socket
from typing import Any, override
from urllib.parse import urlparse

from habitron_client import HabitronError, discover_smarthubs, test_connection
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import CONF_DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

KEY_HOST = "habitron_host"
KEY_TOKEN = "websock_token"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    own_ip = await network.async_get_source_ip(hass)
    host_input = data[KEY_HOST]

    # If the entered IP matches our own IP, store the 'local' sentinel.
    if host_input == own_ip:
        host_input = "local"
        data[KEY_HOST] = "local"

    host_to_test = host_input
    if host_to_test == "local":
        # Resolve the sentinel to our own IP for the probe.
        host_to_test = own_ip

    # Connection test
    try:
        # test_connection has been async since habitron_client 1.0.0.
        result, host_name = await test_connection(host_to_test)
    except socket.gaierror as exc:
        raise HostNotFound from exc
    except ConnectionRefusedError as exc:
        raise CannotConnect from exc
    except (OSError, TimeoutError, HabitronError) as exc:
        # Genuinely-expected connection failures. ``test_connection`` wraps DNS
        # and socket problems into ``HabitronError``; anything else (e.g. a
        # response-processing bug) propagates so the caller's ``unknown`` path
        # surfaces the real fault instead of hiding it as a network error.
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

    VERSION = 1

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
            except HabitronError as err:
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
        if host == CONF_DEFAULT_HOST:
            return await network.async_get_source_ip(self.hass) or host
        with contextlib.suppress(OSError):
            return await self.hass.async_add_executor_job(socket.gethostbyname, host)
        return host.casefold()

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
            entry_host = entry.data.get(KEY_HOST)
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
        """Check if a device with this host or IP is already configured."""
        return (
            await self._async_matching_entry(
                self.hass.config_entries.async_entries(DOMAIN), host, ip
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
        unique_id: str | None = upnp.get(ATTR_UPNP_UDN) or upnp.get(ATTR_UPNP_SERIAL)
        target_device: dict[str, str] | None = None

        if unique_id is None:
            devices = await self._cached_discover()
            target_device = next((d for d in devices if d.get("ip") == host_str), None)
            if target_device:
                unique_id = target_device.get("serial")

        self._discovered_device = target_device or {"ip": host_str}

        if not unique_id:
            _LOGGER.warning(
                "Habitron at %s exposed no UDN/serial; using host as fallback id",
                host_str,
            )
            unique_id = f"habitron_{host_str}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={KEY_HOST: host_str})

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
            list(self._async_current_entries(include_ignore=False)),
            host_str,
            self._discovered_device.get("ip"),
        ):
            if entry.unique_id != unique_id:
                self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
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
            data = {
                KEY_HOST: self._discovered_device.get("ip"),
                KEY_TOKEN: "",
            }
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
            # Canonicalize an own-IP host to the ``local`` sentinel first, so the
            # fallback unique_id matches the host that ``validate_input`` will
            # actually store (it rewrites an own IP to ``local`` only later).
            host_input = user_input[KEY_HOST]
            if host_input == await network.async_get_source_ip(self.hass):
                host_input = "local"
            unique_id: str | None = None
            devices = await self._cached_discover()
            target = next((d for d in devices if d.get("ip") == host_input), None)
            if target:
                unique_id = target.get("serial")
            if unique_id is None:
                unique_id = f"habitron_{host_input}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

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

            default_host = user_input[KEY_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(KEY_HOST, default=default_host): str,
                    vol.Optional(KEY_TOKEN, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class HostNotFound(exceptions.HomeAssistantError):
    """Error to indicate DNS name is not found."""
