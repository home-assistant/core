"""Config flow for the EARN-E P1 Meter integration."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10
VALIDATION_TIMEOUT = 65

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


@dataclass
class DeviceInfo:
    """Information discovered about an EARN-E device."""

    host: str
    serial: str | None = None


class _ListenProtocol(asyncio.DatagramProtocol):
    """UDP protocol that listens for EARN-E P1 packets.

    Optionally filters by host and extracts serial number.
    """

    def __init__(
        self,
        future: asyncio.Future[DeviceInfo],
        host_filter: str | None = None,
    ) -> None:
        """Initialize the listen protocol."""
        self.future = future
        self.host_filter = host_filter

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        if self.future.done():
            return

        source_ip = addr[0]
        if self.host_filter and source_ip != self.host_filter:
            return

        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(payload, dict):
            return

        # Accept packets that look like EARN-E P1 meter data
        if "power_delivered" not in payload and "serial" not in payload:
            return

        self.future.set_result(
            DeviceInfo(
                host=source_ip,
                serial=payload.get("serial"),
            )
        )


class EarnEP1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EARN-E P1 Meter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_info: DeviceInfo | None = None

    async def _async_listen_for_device(
        self,
        host_filter: str | None = None,
        timeout: int = DISCOVERY_TIMEOUT,
    ) -> DeviceInfo | None:
        """Listen for UDP packets and return device info.

        Args:
            host_filter: Only accept packets from this IP address.
            timeout: Seconds to wait before giving up.

        Returns:
            DeviceInfo if a device was found, None on timeout.

        Raises:
            OSError: If the UDP port cannot be opened.

        """
        loop = self.hass.loop
        found: asyncio.Future[DeviceInfo] = loop.create_future()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: _ListenProtocol(found, host_filter),
            local_addr=("0.0.0.0", DEFAULT_PORT),
            allow_broadcast=True,
        )
        try:
            async with asyncio.timeout(timeout):
                return await found
        except TimeoutError:
            return None
        finally:
            transport.close()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input)

        # Attempt auto-discovery before showing manual form
        try:
            info = await self._async_listen_for_device()
        except OSError:
            # Port already in use (e.g. coordinator already listening)
            info = None

        if info:
            self._discovered_info = info
            return await self.async_step_discovery_confirm()

        # Fallback to manual IP entry
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Validate manual IP entry and create config entry."""
        errors: dict[str, str] = {}
        host = user_input[CONF_HOST]
        serial: str | None = None

        try:
            info = await self._async_listen_for_device(
                host_filter=host, timeout=VALIDATION_TIMEOUT
            )
        except OSError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating EARN-E P1 device")
            errors["base"] = "unknown"
        else:
            if info is None:
                errors["base"] = "cannot_connect"
            else:
                serial = info.serial

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        unique_id = serial or host
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"EARN-E P1 ({host})",
            data={CONF_HOST: host, "serial": serial},
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        assert self._discovered_info is not None
        info = self._discovered_info

        if user_input is not None:
            unique_id = info.serial or info.host
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"EARN-E P1 ({info.host})",
                data={CONF_HOST: info.host, "serial": info.serial},
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": info.host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST,
                            default=self._get_reconfigure_entry().data[CONF_HOST],
                        ): str,
                    }
                ),
            )

        errors: dict[str, str] = {}
        host = user_input[CONF_HOST]
        serial: str | None = None

        # During reconfigure, the coordinator already holds the UDP port.
        # Try with reuse_port; if that fails, skip validation (device already proven).
        try:
            info = await self._async_listen_for_device(
                host_filter=host, timeout=VALIDATION_TIMEOUT
            )
        except OSError:
            # Port in use by the running coordinator — skip validation
            info = DeviceInfo(host=host, serial=None)
        except Exception:
            _LOGGER.exception("Unexpected error during reconfigure validation")
            errors["base"] = "unknown"
            info = None

        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=host): str,
                    }
                ),
                errors=errors,
            )

        if info and info.serial:
            serial = info.serial

        entry = self._get_reconfigure_entry()
        # Preserve existing serial if we couldn't get one fresh
        if serial is None:
            serial = entry.data.get("serial")

        unique_id = serial or host
        # Check that no *other* entry has this unique_id
        for other in self._async_current_entries(include_ignore=True):
            if other.entry_id != entry.entry_id and other.unique_id == unique_id:
                return self.async_abort(reason="already_configured")

        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_HOST: host, "serial": serial},
            unique_id=unique_id,
        )
