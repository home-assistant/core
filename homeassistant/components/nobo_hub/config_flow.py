"""Config flow for Nobø Ecohub integration."""

import ipaddress
from typing import TYPE_CHECKING, Any, override

from pynobo import nobo
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import NoboHubConfigEntry
from .const import (
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
    OVERRIDE_TYPE_CONSTANT,
    OVERRIDE_TYPE_NOW,
    SERIAL_LENGTH,
    SERIAL_PREFIX_LENGTH,
)

DATA_NOBO_HUB_IMPL = "nobo_hub_flow_implementation"
DEVICE_INPUT = "device_input"


class NoboHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nobø Ecohub."""

    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_hubs: dict[str, Any] | None = None
        self._hub: str | None = None
        self._mac: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._discovered_hubs is None:
            # Wait 5s — real-world gaps up to ~4s have been observed.
            discovered = dict(await nobo.async_discover_hubs(autodiscover_wait=5.0))
            # Hide hubs that already have a config entry. Include matching on IP
            # as serial prefix is not unique.
            configured = {
                (entry.data[CONF_IP_ADDRESS], entry.unique_id[:SERIAL_PREFIX_LENGTH])
                for entry in self._async_current_entries(include_ignore=False)
                if entry.unique_id
            }
            self._discovered_hubs = {
                ip: prefix
                for ip, prefix in discovered.items()
                if (ip, prefix) not in configured
            }

        if not self._discovered_hubs:
            # No hubs auto discovered
            return await self.async_step_manual()

        if user_input is not None:
            if user_input["device"] == "manual":
                return await self.async_step_manual()
            self._hub = user_input["device"]
            return await self.async_step_selected()

        hubs = self._hubs()
        hubs["manual"] = "Manual"
        data_schema = vol.Schema(
            {
                vol.Required("device"): vol.In(hubs),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of a Nobø Ecohub.

        The MAC from the DHCP packet is set as the flow's temporary
        unique_id so the user can dismiss this discovery via "Ignore",
        and so a previously-ignored hub aborts cleanly on rediscovery.
        The unique_id is replaced with the full 12-digit serial when an
        entry is created.

        Four paths from here:
        - Fast path: a configured entry already has this MAC stored →
          refresh its IP and abort.
        - Device is already ignored.
        - IP+prefix match: listen for the hub's UDP broadcast (15s) to
          learn the 9-digit serial prefix. If a configured entry's
          stored IP and prefix both match the DHCP packet, backfill its
          MAC and abort.
        - Otherwise: route to the `selected` step so the user can
          supply the 3-digit serial suffix.
        """
        self._mac = discovery_info.macaddress
        # Fast path: a configured entry already knows this MAC. Refresh
        # its IP and skip the broadcast wait entirely. Done before
        # `async_set_unique_id` so an ignored entry with the same MAC
        # doesn't block the IP refresh of an active configuration.
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_MAC) == discovery_info.macaddress:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_IP_ADDRESS: discovery_info.ip},
                    reason="already_configured",
                )

        # Use the MAC as the temporary unique_id so the frontend offers an
        # "Ignore" option, and so a previously-ignored MAC correctly aborts
        # the flow here. The MAC is per-device unique (the 9-digit serial
        # prefix would shadow sibling hubs from the same production batch).
        # Replaced with the full 12-digit serial in _create_configuration
        # once the user supplies the suffix.
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured()

        # Wait 15s — when DHCP fires on hub boot, the hub's broadcast
        # service comes up after the DHCPDISCOVER but typically within
        # ~10s. Shorter waits may miss the first post-boot broadcast.
        discovered = await nobo.async_discover_hubs(
            ip=discovery_info.ip, autodiscover_wait=15.0
        )
        if not discovered:
            return self.async_abort(reason="cannot_discover")
        _, serial_prefix = next(iter(discovered))

        # Fallback: a configured entry without a stored MAC (manual or
        # user-picker entry, not yet DHCP-backfilled) is identified by
        # both the stored IP and the 9-digit serial prefix matching the
        # DHCP packet. Requiring IP match prevents clobbering a sibling
        # entry from the same production batch (which shares the prefix).
        # Pynobo's connection-failure rediscovery handles IP changes for
        # non-DHCP-backfilled entries.
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.data.get(CONF_IP_ADDRESS) == discovery_info.ip
                and entry.unique_id
                and entry.unique_id.startswith(serial_prefix)
            ):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_MAC: discovery_info.macaddress},
                    reason="already_configured",
                )

        self._discovered_hubs = {discovery_info.ip: serial_prefix}
        self._hub = discovery_info.ip
        return await self.async_step_selected()

    async def async_step_selected(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration of a selected discovered device."""
        errors = {}
        if TYPE_CHECKING:
            assert self._discovered_hubs
            assert self._hub
        if user_input is not None:
            serial_prefix = self._discovered_hubs[self._hub]
            serial_suffix = user_input["serial_suffix"]
            serial = f"{serial_prefix}{serial_suffix}"
            try:
                return await self._create_configuration(serial, self._hub)
            except NoboHubConnectError as error:
                errors["base"] = error.msg

        user_input = user_input or {}
        return self.async_show_form(
            step_id="selected",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "serial_suffix", default=user_input.get("serial_suffix")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hub": self._format_hub(self._hub, self._discovered_hubs[self._hub])
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing hub.

        Only the IP address is editable. When the entry is not loaded,
        the new IP is probed here before updating. When the entry is
        loaded, probing is skipped to avoid competing with the active
        connection for the hub's limited concurrent-connection slots;
        the reload's ``async_setup_entry`` re-validates the updated IP.
        """
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_ip = user_input[CONF_IP_ADDRESS]
            is_loaded = reconfigure_entry.state is ConfigEntryState.LOADED
            try:
                ipaddress.ip_address(new_ip)
            except ValueError:
                errors[CONF_IP_ADDRESS] = "invalid_ip"
            else:
                try:
                    # Probe the new IP only when the integration is not currently
                    # loaded — if it were, the running connection would compete
                    # with the probe for the hub's limited concurrent-connection
                    # slots.
                    if not is_loaded:
                        await self._test_connection(
                            reconfigure_entry.data[CONF_SERIAL], new_ip
                        )
                except NoboHubConnectError as error:
                    # The serial is fixed in reconfigure, so blame the IP rather
                    # than the (uneditable) serial number.
                    errors[CONF_IP_ADDRESS] = (
                        "cannot_connect_ip"
                        if error.msg == "cannot_connect"
                        else error.msg
                    )
                else:
                    if new_ip == reconfigure_entry.data[CONF_IP_ADDRESS] and is_loaded:
                        # No-op: IP unchanged and the running integration already
                        # proves it works. Skip the reload to avoid a needless
                        # reconnect.
                        return self.async_abort(reason="reconfigure_successful")
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates={CONF_IP_ADDRESS: new_ip},
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_IP_ADDRESS): str}),
                user_input or reconfigure_entry.data,
            ),
            errors=errors,
            description_placeholders={
                CONF_SERIAL: reconfigure_entry.data[CONF_SERIAL],
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration of an undiscovered device."""
        errors = {}
        if user_input is not None:
            serial = user_input[CONF_SERIAL]
            ip_address = user_input[CONF_IP_ADDRESS]
            try:
                return await self._create_configuration(serial, ip_address)
            except NoboHubConnectError as error:
                errors["base"] = error.msg

        user_input = user_input or {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL, default=user_input.get(CONF_SERIAL)): str,
                    vol.Required(
                        CONF_IP_ADDRESS, default=user_input.get(CONF_IP_ADDRESS)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _create_configuration(
        self, serial: str, ip_address: str
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        name = await self._test_connection(serial, ip_address)
        return self.async_create_entry(
            title=name,
            data={
                CONF_SERIAL: serial,
                CONF_IP_ADDRESS: ip_address,
                CONF_MAC: self._mac,
            },
        )

    async def _test_connection(self, serial: str, ip_address: str) -> str:
        if len(serial) != SERIAL_LENGTH or not serial.isdigit():
            raise NoboHubConnectError("invalid_serial")
        try:
            ipaddress.ip_address(ip_address)
        except ValueError as err:
            raise NoboHubConnectError("invalid_ip") from err
        hub = nobo(serial=serial, ip=ip_address, discover=False, synchronous=False)
        # pynobo distinguishes the two failure modes: TCP-level errors
        # (wrong IP, hub offline, port closed) raise OSError, while a
        # successful TCP connection followed by a handshake REJECT
        # (serial mismatch) returns False.
        try:
            if not await hub.async_connect_hub(ip_address, serial):
                raise NoboHubConnectError("cannot_connect")
            return hub.hub_info["name"]
        except OSError as err:
            raise NoboHubConnectError("cannot_connect_ip") from err
        finally:
            await hub.close()

    @staticmethod
    def _format_hub(ip, serial_prefix):
        return f"{serial_prefix}XXX ({ip})"

    def _hubs(self):
        return {
            ip: self._format_hub(ip, serial_prefix)
            for ip, serial_prefix in self._discovered_hubs.items()
        }

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: NoboHubConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class NoboHubConnectError(HomeAssistantError):
    """Error with connecting to Nobø Ecohub."""

    def __init__(self, msg) -> None:
        """Instantiate error."""
        super().__init__()
        self.msg = msg


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handles options flow for the component."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            data = {
                CONF_OVERRIDE_TYPE: user_input.get(CONF_OVERRIDE_TYPE),
            }
            return self.async_create_entry(title="", data=data)

        override_type = self.config_entry.options.get(
            CONF_OVERRIDE_TYPE, OVERRIDE_TYPE_CONSTANT
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_OVERRIDE_TYPE, default=override_type): SelectSelector(
                    SelectSelectorConfig(
                        options=[OVERRIDE_TYPE_CONSTANT, OVERRIDE_TYPE_NOW],
                        translation_key=CONF_OVERRIDE_TYPE,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
