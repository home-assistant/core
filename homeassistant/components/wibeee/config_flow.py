"""Config flow for Wibeee energy monitor."""

from __future__ import annotations

from datetime import timedelta
import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import aiohttp
from pywibeee import WibeeeAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import WibeeeConfigEntry
from .const import (
    CONF_AUTO_CONFIGURE,
    CONF_MAC_ADDRESS,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_HA_PORT = 8123


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    """Validate the user input allows us to connect.

    Returns:
        A tuple of (title, unique_id, data).
    """
    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, data[CONF_HOST])

    try:
        device = await api.async_fetch_device_info(retries=3)
    except (TimeoutError, aiohttp.ClientError) as exc:
        raise NoDeviceInfo(f"Cannot connect: {exc}") from exc

    if device is None:
        raise NoDeviceInfo("No device info received")

    # Normalize MAC for unique_id consistency
    mac_clean = device.mac_addr_formatted.replace(":", "").lower()

    return (
        f"Wibeee {device.mac_addr_short}",
        mac_clean,
        {
            CONF_HOST: data[CONF_HOST],
            CONF_MAC_ADDRESS: mac_clean,
            CONF_WIBEEE_ID: device.wibeee_id,
        },
    )


def _is_routable_ip(ip: str) -> bool:
    """Check if IP is a valid routable address (not loopback/multicast/link-local)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_loopback
        or addr.is_multicast
        or addr.is_link_local
        or addr.is_unspecified
    )


async def _async_configure_device(hass: HomeAssistant, host: str) -> bool:
    """Configure the device for local push."""
    try:
        local_ip = await _get_local_ip(hass)
        if not _is_routable_ip(local_ip):
            return False

        ha_port = _get_ha_port(hass)
        session = async_get_clientsession(hass)
        api = WibeeeAPI(session, host, timeout=timedelta(seconds=15))
        success = await api.async_configure_push_server(local_ip, ha_port)
        if success:
            _LOGGER.debug(
                "Auto-configured WiBeee at %s to push to %s:%d", host, local_ip, ha_port
            )
            return True
    except TimeoutError, aiohttp.ClientError, OSError:
        pass
    return False


def _get_local_ip_sync() -> str:
    """Determine local IP via socket (blocking, run in executor)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return str(s.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


async def _get_local_ip(hass: HomeAssistant) -> str:
    """Determine the local IP of the Home Assistant instance."""
    try:
        from homeassistant.components.network import (  # noqa: PLC0415
            async_get_source_ip,
        )

        ip = await async_get_source_ip(hass)
        if ip is not None:
            return ip
    except ImportError, HomeAssistantError, OSError:
        pass

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
                pass
    except ImportError, HomeAssistantError, OSError:
        pass

    return await hass.async_add_executor_job(_get_local_ip_sync)


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get the port Home Assistant's HTTP server is listening on."""
    try:
        from homeassistant.helpers.network import get_url  # noqa: PLC0415

        url = get_url(hass, prefer_external=False)
        port = urlparse(url).port
        if port is not None:
            return port
    except ImportError, HomeAssistantError, OSError:
        pass

    return DEFAULT_HA_PORT


class WibeeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wibeee config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_data: dict[str, Any] = {}
        self._discovered_host: str | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle DHCP discovery of a Wibeee device."""
        host = discovery_info.ip
        mac = discovery_info.macaddress.replace(":", "").lower()

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        session = async_get_clientsession(self.hass)
        api = WibeeeAPI(session, host, timeout=timedelta(seconds=5))
        try:
            is_wibeee = await api.async_check_connection()
            if not is_wibeee:
                return self.async_abort(reason="not_wibeee_device")
        except TimeoutError, aiohttp.ClientError:
            return self.async_abort(reason="not_wibeee_device")

        self._discovered_host = host
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: User enters the device IP."""
        errors: dict[str, str] = {}

        if user_input is None and self._discovered_host:
            user_input = {CONF_HOST: self._discovered_host}

        if user_input is not None:
            try:
                title, unique_id, data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates=user_input)

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

        default_host = (user_input or {}).get(CONF_HOST) or self._discovered_host or ""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=default_host): str}
            ),
            errors=errors,
        )

    async def async_step_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Choose update mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mode = user_input.get(CONF_UPDATE_MODE, MODE_LOCAL_PUSH)
            auto_configure = user_input.get(CONF_AUTO_CONFIGURE, False)

            if mode == MODE_LOCAL_PUSH and auto_configure:
                if not await _async_configure_device(
                    self.hass, self._user_data[CONF_HOST]
                ):
                    errors["base"] = "auto_configure_failed"

            if not errors:
                title = self._user_data.pop("_title")
                return self.async_create_entry(
                    title=title,
                    data=self._user_data,
                    options={CONF_UPDATE_MODE: mode},
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
                                    label="Local Push", value=MODE_LOCAL_PUSH
                                ),
                                SelectOptionDict(label="Polling", value=MODE_POLLING),
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
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                _, unique_id, data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=data
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
                    ): str
                }
            ),
            errors=errors,
        )


class WibeeeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

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

            if new_mode == MODE_LOCAL_PUSH and auto_configure:
                if not await _async_configure_device(
                    self.hass, self.config_entry.data[CONF_HOST]
                ):
                    errors["base"] = "auto_configure_failed"

            if not errors:
                return self.async_create_entry(
                    title="", data={CONF_UPDATE_MODE: new_mode}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_UPDATE_MODE, default=current_mode
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(
                                        label="Local Push", value=MODE_LOCAL_PUSH
                                    ),
                                    SelectOptionDict(
                                        label="Polling", value=MODE_POLLING
                                    ),
                                ],
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional(
                            CONF_AUTO_CONFIGURE, default=False
                        ): BooleanSelector(),
                    }
                ),
                options,
            ),
            errors=errors,
        )


class NoDeviceInfo(HomeAssistantError):
    """Error to indicate we could not get info from a Wibeee device."""
