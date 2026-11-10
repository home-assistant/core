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
    async_build_hub,
    discover_smarthubs,
    get_host_ip,
    test_connection,
)
import probatio

from homeassistant import config_entries, exceptions
from homeassistant.components import network
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_DEFAULT_HOST, DOMAIN
from .coordinator import async_hub_macs

_LOGGER = logging.getLogger(__name__)


async def _async_hub_mac(host: str) -> str | None:
    """Return the hub's LAN MAC, or ``None`` when it reports none."""
    try:
        async with HabitronClient(host) as client:
            hub = await async_build_hub(client)
    except (HabitronError, OSError) as err:
        raise CannotConnect from err
    if not hub.uid:
        _LOGGER.debug(
            "Hub at %s reported %r, which is no usable MAC", host, hub.lan_mac
        )
        return None
    return hub.uid


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host_input = data[CONF_HOST]

    # Any of HA's own addresses means a hub on this machine.
    own_ips = {str(ip) for ip in await network.async_get_enabled_source_ips(hass)}
    if host_input in own_ips:
        host_input = CONF_DEFAULT_HOST
        data[CONF_HOST] = CONF_DEFAULT_HOST

    host_to_test = host_input
    if host_to_test == CONF_DEFAULT_HOST:
        host_to_test = await network.async_get_source_ip(hass)

    # Resolve first: ``test_connection`` reports a DNS failure like any other error.
    try:
        await get_host_ip(host_to_test)
    except HabitronConnectionError as exc:
        raise HostNotFound from exc

    try:
        result, host_name = await test_connection(host_to_test)
    except (OSError, TimeoutError, HabitronError) as exc:
        raise CannotConnect from exc

    if not result:
        raise CannotConnect

    # The name is empty when the hub does not answer the metadata query.
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
        """Run the network discovery once per flow."""
        if self._udp_devices is None:
            try:
                self._udp_devices = await discover_smarthubs()
            except (HabitronError, OSError) as err:
                _LOGGER.debug("SmartHub discovery failed: %s", err)
                self._udp_devices = []
        return self._udp_devices

    async def _async_canonical_host(self, host: str) -> str:
        """Return a comparable form of ``host``."""
        own_ips = {
            str(ip) for ip in await network.async_get_enabled_source_ips(self.hass)
        }
        if host == CONF_DEFAULT_HOST or host in own_ips:
            return CONF_DEFAULT_HOST
        with contextlib.suppress(OSError):
            resolved = await self.hass.async_add_executor_job(
                socket.gethostbyname, host
            )
            if resolved in own_ips:
                return CONF_DEFAULT_HOST
            return resolved
        return host.casefold()

    async def _async_stored_host(self, host: str) -> str:
        """Return ``host`` in the form an entry stores it."""
        own_ips = {
            str(ip) for ip in await network.async_get_enabled_source_ips(self.hass)
        }
        return CONF_DEFAULT_HOST if host in own_ips else host

    async def _async_probe_host(self, host: str) -> str:
        """Return an IP address the hub client can dial."""
        if host == CONF_DEFAULT_HOST:
            return await network.async_get_source_ip(self.hass)
        with contextlib.suppress(OSError):
            return await self.hass.async_add_executor_job(socket.gethostbyname, host)
        return host

    async def _async_hub_identity(self, host: str) -> str | None:
        """Return the hub's MAC as its unique id, or ``None``."""
        return await _async_hub_mac(await self._async_probe_host(host))

    async def _async_matching_entry(
        self,
        entries: list[config_entries.ConfigEntry],
        *hosts: str | None,
    ) -> config_entries.ConfigEntry | None:
        """Return the entry already configured for one of ``hosts``, if any."""
        candidates = {host for host in hosts if host}
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
        """Check if a device with this host or IP is already configured."""
        return (
            await self._async_matching_entry(
                list(self._async_current_entries()), host, ip
            )
            is not None
        )

    def _async_schedule_reload_if_retrying(
        self, entry: config_entries.ConfigEntry
    ) -> None:
        """Reload an entry in setup retry, which has no update listener yet."""
        if entry.state is config_entries.ConfigEntryState.SETUP_RETRY:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

    def _async_entry_by_hub_identity(
        self, unique_id: str
    ) -> config_entries.ConfigEntry | None:
        """Return the entry bound to the hub with this MAC, preferring a live one."""
        bound = [
            entry
            for entry in self._async_current_entries()
            if unique_id in async_hub_macs(self.hass, entry)
        ]
        return next(
            (entry for entry in bound if entry.source != config_entries.SOURCE_IGNORE),
            next(iter(bound), None),
        )

    async def _async_abort_if_host_configured(
        self, host: str, *, unique_id: str
    ) -> config_entries.ConfigFlowResult | None:
        """Abort when the hub is configured under an entry not keyed by its MAC."""
        # Await first, so the bindings checked below cannot change before the abort.
        stored_host = await self._async_stored_host(host)
        by_address = await self._async_matching_entry(
            [
                candidate
                for candidate in self._async_current_entries()
                if not async_hub_macs(self.hass, candidate)
            ],
            host,
        )

        # An entry bound to another MAC is another hub, even at the same address.
        entry = self._async_entry_by_hub_identity(unique_id)
        if (
            entry is None
            and by_address is not None
            and by_address in self._async_current_entries()
            and not async_hub_macs(self.hass, by_address)
        ):
            entry = by_address
        if entry is None:
            return None
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: stored_host}
        )
        self._async_schedule_reload_if_retrying(entry)
        return self.async_abort(reason="already_configured")

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

        self._discovered_device = {"ip": host_str}

        try:
            unique_id = await self._async_hub_identity(host_str)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        if unique_id is None:
            return self.async_abort(reason="no_mac_address")

        await self.async_set_unique_id(unique_id)
        # Before the unique id check, so a live entry wins over an ignored one.
        if (
            result := await self._async_abort_if_host_configured(
                host_str, unique_id=unique_id
            )
        ) is not None:
            return result
        # The entry's update listener does the reload.
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
            host = self._discovered_device["ip"]
            data = {CONF_HOST: host}
            try:
                info = await validate_input(self.hass, data)
                # Probe again: the address may now belong to another hub.
                unique_id = await self._async_hub_identity(host)
            except CannotConnect, HostNotFound:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                if unique_id is None:
                    return self.async_abort(reason="no_mac_address")
                await self.async_set_unique_id(unique_id)
                stored_host = await self._async_stored_host(host)
                if (
                    result := await self._async_abort_if_host_configured(
                        host, unique_id=unique_id
                    )
                ) is not None:
                    return result
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: stored_host}, reload_on_update=False
                )
                return self.async_create_entry(title=info["title"], data=data)

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

        if user_input is None:
            discovered = await self._cached_discover()

            valid_devices = [
                d
                for d in discovered
                if not await self._is_device_already_configured(d.get("ip", ""))
            ]
            if valid_devices:
                default_host = valid_devices[0].get("ip", CONF_DEFAULT_HOST)

        if user_input is not None:
            host_input = user_input[CONF_HOST]

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
                    errors["base"] = "no_mac_address"
                else:
                    await self.async_set_unique_id(unique_id)
                    stored_host = await self._async_stored_host(host_input)
                    # Core skips the retry backoff for discovery sources only.
                    if (
                        known
                        := self.hass.config_entries.async_entry_for_domain_unique_id(
                            DOMAIN, unique_id
                        )
                    ) is not None and (
                        known.state is config_entries.ConfigEntryState.SETUP_RETRY
                    ):
                        self.hass.config_entries.async_update_entry(
                            known, data={**known.data, CONF_HOST: stored_host}
                        )
                        self._async_schedule_reload_if_retrying(known)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: stored_host},
                        reload_on_update=False,
                    )
                    if (
                        result := await self._async_abort_if_host_configured(
                            host_input, unique_id=unique_id
                        )
                    ) is not None:
                        return result
                    return self.async_create_entry(title=info["title"], data=user_input)

            default_host = user_input[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST, default=default_host): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class HostNotFound(exceptions.HomeAssistantError):
    """Error to indicate DNS name is not found."""
