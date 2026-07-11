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

    # Basic validation
    if len(host_to_test) < 4:
        raise InvalidHost

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

    return {"title": host_name}


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

    def _is_device_already_configured(self, host: str, ip: str | None = None) -> bool:
        """Check if a device with this host or IP is already configured."""
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in existing_entries:
            entry_host = entry.data.get(KEY_HOST)
            if entry_host == host or (ip and entry_host == ip):
                return True
        return False

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
        candidate_hosts: set[str | None] = {
            host_str,
            self._discovered_device.get("ip"),
        }
        with contextlib.suppress(OSError):
            candidate_hosts.add(
                await self.hass.async_add_executor_job(socket.gethostbyname, host_str)
            )
        # An entry configured as the ``local`` sentinel runs on the same machine
        # as Home Assistant, so its LAN address is one of HA's own source IPs.
        # Ask HA directly — this matches even when the hub is briefly unreachable
        # (e.g. rebooting during startup) and the entry is not yet loaded.
        local_is_candidate = (
            await network.async_get_source_ip(self.hass) in candidate_hosts
        )
        for entry in self._async_current_entries(include_ignore=False):
            host_conf = entry.data.get(KEY_HOST)
            if host_conf in candidate_hosts or (
                host_conf == CONF_DEFAULT_HOST and local_is_candidate
            ):
                if entry.unique_id != unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=unique_id
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
            data = {
                KEY_HOST: self._discovered_device.get("ip"),
                KEY_TOKEN: "",
            }
            try:
                info = await validate_input(self.hass, data)
                return self.async_create_entry(title=info["title"], data=data)
            except CannotConnect:
                # A briefly-offline hub should be retryable, not aborted.
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
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
                if not self._is_device_already_configured(d.get("ip", ""))
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
            if self._is_device_already_configured(user_input[KEY_HOST], probed_ip):
                return self.async_abort(reason="already_configured")

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HostNotFound:
                errors["base"] = "host_not_found"
            except InvalidHost:
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


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
