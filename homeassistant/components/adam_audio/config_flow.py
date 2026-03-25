"""Config flow for ADAM Audio.

Two entry points:
  1. Zeroconf auto-discovery  — HA detects an _oca._udp.local. service and
     triggers async_step_zeroconf.  The user just confirms.
  2. Manual                   — User adds the integration from the UI and
     types in an IP address + port.

In both cases we attempt a real connection to the device to verify
reachability and fetch the human-readable description ("Left", "Right", …)
before creating the config entry.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import AdamAudioClient
from .const import (
    CONF_DESCRIPTION,
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class AdamAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow that handles both zeroconf discovery and manual IP entry.

    A unique_id is set to the device's serial number (preferred) or hardware
    name so that the same physical speaker is never registered twice, even if
    its IP address changes and it is re-discovered.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery: dict[str, Any] = {}

    # ── Manual entry ──────────────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (manual IP entry)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))

            result = await self._async_try_connect(host, port)
            if result is None:
                errors["base"] = "cannot_connect"
            else:
                device_name, description, serial = result
                await self.async_set_unique_id(serial or device_name)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                return self.async_create_entry(
                    title=description or device_name,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_DEVICE_NAME: device_name,
                        CONF_DESCRIPTION: description,
                        CONF_SERIAL: serial,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_MANUAL_SCHEMA,
            errors=errors,
            description_placeholders={"default_port": str(DEFAULT_PORT)},
        )

    # ── Zeroconf discovery ────────────────────────────────────────────────────

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an _oca._udp.local. service."""
        host: str = discovery_info.host
        port: int = discovery_info.port or DEFAULT_PORT

        # Derive a stable device_id from the mDNS hostname.
        # hostname is like "ASeries-41472b.local." → strip to "ASeries-41472b"
        device_id: str = (
            discovery_info.hostname.rstrip(".")
            .removesuffix(".local")
            .removesuffix(".local.")
        )
        if not device_id:
            device_id = host.replace(".", "_")

        # Attempt to connect and retrieve device metadata (including serial).
        result = await self._async_try_connect(host, port)
        if result is not None:
            _device_name, description, serial = result
        else:
            _device_name, description, serial = device_id, device_id, ""

        # Prefer serial (stable, device-embedded) as unique_id; fall back to hostname.
        await self.async_set_unique_id(serial or device_id)
        # If this device is already configured, just update its IP/port silently.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        self._discovery = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_DEVICE_NAME: _device_name or device_id,
            CONF_DESCRIPTION: description,
            CONF_SERIAL: serial,
        }

        self.context["title_placeholders"] = {
            "name": description or device_id,
            "host": host,
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirmation step shown after zeroconf discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery.get(CONF_DESCRIPTION)
                or self._discovery.get(CONF_DEVICE_NAME, "ADAM Audio"),
                data=self._discovery,
            )

        description = self._discovery.get(CONF_DESCRIPTION, "")
        host = self._discovery.get(CONF_HOST, "")

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": description or self._discovery.get(CONF_DEVICE_NAME, ""),
                "host": host,
            },
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _async_try_connect(
        self, host: str, port: int
    ) -> tuple[str, str, str] | None:
        """Open a temporary connection to verify the device is reachable.

        Returns (device_name, description, serial) on success, None on failure.
        """
        client = AdamAudioClient(self.hass, host, port)
        try:
            connected = await client.async_setup()
            if not connected:
                return None
        except OSError, TimeoutError, ValueError, RuntimeError:
            LOGGER.debug(
                "Connection attempt to %s:%d failed", host, port, exc_info=True
            )
            return None
        else:
            return client.device_name, client.description, client.serial
        finally:
            await client.async_shutdown()
