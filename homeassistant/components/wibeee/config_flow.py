"""Config flow for Wibeee integration."""

from __future__ import annotations

from datetime import timedelta
import ipaddress
import logging
import socket
from typing import Any, cast
from urllib.parse import urlparse

import aiohttp
from pywibeee import WibeeeAPI
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import WibeeeConfigEntry
from .const import (
    CONF_AUTO_CONFIGURE,
    CONF_HOST,
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DEFAULT_HA_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_mac(mac: str) -> str:
    """Normalize MAC address for use as unique_id."""
    return mac.replace(":", "").lower()


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, str]
) -> tuple[str, str, dict[str, str]]:
    """Validate the user input and fetch device info.

    Returns (title, unique_id, data_dict).
    Raises NoDeviceInfo if the device cannot be reached.
    """
    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, user_input[CONF_HOST], timeout=timedelta(seconds=5))

    # First check if it's a Wibeee device
    async def _check_connection() -> bool:
        try:
            return await api.async_check_connection()
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise NoDeviceInfo(f"Cannot connect: {exc}") from exc

    is_wibeee = await _check_connection()
    if not is_wibeee:
        raise NoDeviceInfo("Device did not respond as a Wibeee")

    # Fetch device info
    try:
        device = await api.async_fetch_device_info(retries=3)
    except (TimeoutError, aiohttp.ClientError) as exc:
        raise NoDeviceInfo(f"Cannot get device info: {exc}") from exc

    if device is None:
        raise NoDeviceInfo("Device returned no info")

    unique_id = _normalize_mac(device.mac_addr_formatted)
    name = f"Wibeee {device.mac_addr_short}"

    return (
        name,
        unique_id,
        {
            CONF_HOST: user_input[CONF_HOST],
            CONF_MAC_ADDRESS: device.mac_addr_formatted,
            CONF_WIBEEE_ID: device.wibeee_id,
        },
    )


def _get_local_ip_sync() -> str:
    """Determine local IP via socket (blocking, run in executor)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return cast(str, s.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


async def _get_local_ip(hass: HomeAssistant) -> str:
    """Determine the local IP of the Home Assistant instance.

    Uses a 3-tier fallback strategy:
    1. network component's async_get_source_ip (most reliable, HA-recommended)
    2. helpers.network.get_url parsed hostname (lightweight, no component dep)
    3. Raw socket probe (last resort, blocking via executor)
    """
    # 1. Preferred: network component (may not be loaded)
    try:
        from homeassistant.components.network import (  # noqa: PLC0415
            async_get_source_ip,
        )

        ip = await async_get_source_ip(hass)
        if ip is not None:
            return ip
    except (ImportError, HomeAssistantError, OSError):
        pass

    # 2. URL helper (lightweight, does not require network component)
    try:
        from homeassistant.helpers.network import get_url  # noqa: PLC0415

        url = get_url(hass, prefer_external=False)
        host = urlparse(url).hostname
        if host is not None:
            try:
                addr = ipaddress.ip_address(host)
                if not addr.is_loopback:
                    return host
            except ValueError:
                # Not an IP literal (e.g. hostname) -- usable as-is
                return host
    except (ImportError, HomeAssistantError, OSError):
        pass

    # 3. Fallback: raw socket probe (blocking, run in executor)
    return await hass.async_add_executor_job(_get_local_ip_sync)


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get the port Home Assistant's HTTP server is listening on.

    Uses helpers.network.get_url to read the configured internal URL.
    Falls back to DEFAULT_HA_PORT (8123).
    """
    try:
        from homeassistant.helpers.network import get_url  # noqa: PLC0415

        url = get_url(hass, prefer_external=False)
        port = urlparse(url).port
        if port is not None:
            return port
    except (ImportError, HomeAssistantError, OSError):
        pass

    return DEFAULT_HA_PORT


class WibeeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wibeee config flow.

    Step 1 (user): Enter device IP (or auto-discovered via DHCP)
    Step 2 (mode): Choose update mode (local push or polling)
    """

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_data: dict[str, str] = {}
        self._discovered_host: str | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle DHCP discovery of a Wibeee device.

        Triggered when HA detects a device with MAC prefix 00:1E:C0
        (Circutor SA / Smilics).
        """
        host = discovery_info.ip
        mac = discovery_info.macaddress.replace(":", "").lower()

        _LOGGER.debug(
            "DHCP discovery: Wibeee device found at %s (MAC: %s)",
            host,
            mac,
        )

        # Check if already configured by MAC
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Verify it's really a Wibeee
        session = async_get_clientsession(self.hass)
        api = WibeeeAPI(session, host, timeout=timedelta(seconds=5))
        try:
            is_wibeee = await api.async_check_connection()
            if not is_wibeee:
                return self.async_abort(reason="not_wibeee_device")
        except (TimeoutError, aiohttp.ClientError):
            return self.async_abort(reason="no_device_info")

        self._discovered_host = host
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: User enters the device IP (or confirms discovered IP)."""
        errors: dict[str, str] = {}

        # If DHCP discovered a host, use it as default
        if user_input is None and self._discovered_host:
            user_input = {CONF_HOST: self._discovered_host}

        if user_input is not None:
            try:
                title, unique_id, data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates=user_input)

                # Store data and move to mode selection
                self._user_data = data
                self._user_data["_title"] = title
                return await self.async_step_mode()

            except AbortFlow:
                raise

            except NoDeviceInfo:
                errors[CONF_HOST] = "no_device_info"

            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"

        default_host = (user_input or {}).get(CONF_HOST) or self._discovered_host
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=default_host,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Choose update mode (polling or local push)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mode = user_input.get(CONF_UPDATE_MODE, MODE_LOCAL_PUSH)
            auto_configure = user_input.get(CONF_AUTO_CONFIGURE, False)

            # If local push + auto-configure, configure the device now
            if mode == MODE_LOCAL_PUSH and auto_configure:
                try:
                    local_ip = await _get_local_ip(self.hass)
                    ha_port = _get_ha_port(self.hass)
                    session = async_get_clientsession(self.hass)
                    api = WibeeeAPI(
                        session,
                        self._user_data[CONF_HOST],
                        timeout=timedelta(seconds=15),
                    )
                    success = await api.async_configure_push_server(local_ip, ha_port)
                    if not success:
                        errors["base"] = "auto_configure_failed"
                    else:
                        _LOGGER.debug(
                            "Auto-configured WiBeee to push to %s:%d",
                            local_ip,
                            ha_port,
                        )
                except (TimeoutError, aiohttp.ClientError, OSError):
                    _LOGGER.debug(
                        "Failed to auto-configure WiBeee at %s",
                        self._user_data[CONF_HOST],
                        exc_info=True,
                    )
                    errors["base"] = "auto_configure_failed"

            if not errors:
                title = self._user_data.pop("_title")
                options = {CONF_UPDATE_MODE: mode}
                if mode == MODE_POLLING:
                    options[CONF_SCAN_INTERVAL] = int(
                        DEFAULT_SCAN_INTERVAL.total_seconds()
                    )
                return self.async_create_entry(
                    title=title,
                    data=self._user_data,
                    options=options,
                )

        return self.async_show_form(
            step_id="mode",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_MODE, default=MODE_LOCAL_PUSH
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    label="Local Push",
                                    value=MODE_LOCAL_PUSH,
                                ),
                                SelectOptionDict(
                                    label="Polling",
                                    value=MODE_POLLING,
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_AUTO_CONFIGURE, default=True): BooleanSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: WibeeeConfigEntry,
    ) -> WibeeeOptionsFlowHandler:
        """Get the options flow handler."""
        return WibeeeOptionsFlowHandler()

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the device host."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                _, unique_id, data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=data,
                )
            except AbortFlow:
                raise
            except NoDeviceInfo:
                errors[CONF_HOST] = "no_device_info"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data.get(CONF_HOST, ""),
                    ): str,
                }
            ),
            errors=errors,
        )


class WibeeeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Wibeee.

    Allows switching between polling and local push modes,
    and configuring polling interval or auto-configuring push.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Main options step."""
        errors: dict[str, str] = {}
        options = dict(self.config_entry.options)
        current_mode = options.get(CONF_UPDATE_MODE, MODE_LOCAL_PUSH)

        if user_input is not None:
            new_mode = user_input.get(CONF_UPDATE_MODE, current_mode)
            auto_configure = user_input.get(CONF_AUTO_CONFIGURE, False)

            # If switching to local push with auto-configure
            if new_mode == MODE_LOCAL_PUSH and auto_configure:
                try:
                    local_ip = await _get_local_ip(self.hass)
                    ha_port = _get_ha_port(self.hass)
                    session = async_get_clientsession(self.hass)
                    api = WibeeeAPI(
                        session,
                        self.config_entry.data[CONF_HOST],
                        timeout=timedelta(seconds=15),
                    )
                    success = await api.async_configure_push_server(local_ip, ha_port)
                    if not success:
                        errors["base"] = "auto_configure_failed"
                except (TimeoutError, aiohttp.ClientError, OSError):
                    _LOGGER.debug(
                        "Failed to auto-configure WiBeee at %s",
                        self.config_entry.data[CONF_HOST],
                        exc_info=True,
                    )
                    errors["base"] = "auto_configure_failed"

            if not errors:
                new_options = {CONF_UPDATE_MODE: new_mode}
                if new_mode == MODE_POLLING:
                    new_options[CONF_SCAN_INTERVAL] = user_input.get(
                        CONF_SCAN_INTERVAL,
                        int(DEFAULT_SCAN_INTERVAL.total_seconds()),
                    )
                return self.async_create_entry(title="", data=new_options)

        # Build schema dynamically based on current mode
        schema_dict: dict[vol.Marker, object] = {
            vol.Required(CONF_UPDATE_MODE, default=current_mode): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            label="Local Push",
                            value=MODE_LOCAL_PUSH,
                        ),
                        SelectOptionDict(
                            label="Polling",
                            value=MODE_POLLING,
                        ),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        # Always show polling interval so users can set it when switching modes
        schema_dict[
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=int(
                    options.get(
                        CONF_SCAN_INTERVAL,
                        int(DEFAULT_SCAN_INTERVAL.total_seconds()),
                    )
                ),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=300,
                unit_of_measurement="seconds",
                mode=NumberSelectorMode.BOX,
            )
        )

        # Show auto-configure option for local push
        schema_dict[vol.Optional(CONF_AUTO_CONFIGURE, default=False)] = (
            BooleanSelector()
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema_dict),
                options,
            ),
            errors=errors,
        )


class NoDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we could not get info from a Wibeee device."""
