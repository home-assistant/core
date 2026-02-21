"""Config flow for the iNet Radio integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from inet_control import RadioManager
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_DESCRIPTION,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from .const import CONF_MODEL_DESCRIPTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

MANUAL_ENTRY = "manual"
DISCOVERY_TIMEOUT = 3.0

STEP_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class INetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iNet Radio."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_radios: dict[str, str] = {}
        self._host: str | None = None
        self._name: str | None = None
        self._model: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step with discovery."""
        if user_input is not None:
            selected = user_input.get("device", MANUAL_ENTRY)
            if selected == MANUAL_ENTRY:
                return await self.async_step_manual()
            return await self._async_validate_and_create(selected)

        # Discover radios on the network
        self._discovered_radios = await self._async_discover_radios()

        if not self._discovered_radios:
            return await self.async_step_manual()

        # Build selection options
        device_options = {
            ip: f"{name} ({ip})" for ip, name in self._discovered_radios.items()
        }
        device_options[MANUAL_ENTRY] = "Enter IP address manually"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device"): vol.In(device_options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input[CONF_HOST])

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""
        if not discovery_info.ssdp_location or not (
            host := urlparse(discovery_info.ssdp_location).hostname
        ):
            return self.async_abort(reason="cannot_connect")

        serial = discovery_info.upnp.get(ATTR_UPNP_SERIAL)
        if not serial:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(format_mac(serial))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        manager = RadioManager()
        try:
            await manager.start()
            await manager.connect(host, timeout=5.0)
        except OSError, TimeoutError:
            return self.async_abort(reason="cannot_connect")
        finally:
            await manager.stop()

        self._host = host
        self._name = discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
        self._model = discovery_info.upnp.get(ATTR_UPNP_MODEL_DESCRIPTION)
        self.context["title_placeholders"] = {"name": self._name or host}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of SSDP discovery."""
        if user_input is not None:
            assert self._host is not None
            entry_data: dict[str, str] = {CONF_HOST: self._host}
            if self._model:
                entry_data[CONF_MODEL_DESCRIPTION] = self._model
            return self.async_create_entry(
                title=self._name or f"iNet Radio ({self._host})",
                data=entry_data,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._name or self._host or ""},
        )

    async def _async_validate_and_create(self, host: str) -> ConfigFlowResult:
        """Validate connection and create config entry."""
        errors: dict[str, str] = {}
        manager = RadioManager()
        try:
            await manager.start()
            radio = await manager.connect(host, timeout=5.0)

            if not radio.mac:
                mac_received = asyncio.Event()

                def _on_update() -> None:
                    if radio.mac:
                        mac_received.set()

                unsub = radio.register_callback(_on_update)
                try:
                    async with asyncio.timeout(3.0):
                        await mac_received.wait()
                except TimeoutError:
                    pass
                finally:
                    unsub()
        except TimeoutError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during connection")
            errors["base"] = "unknown"
        else:
            mac_or_serial = radio.serial or radio.mac
            if not mac_or_serial:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(format_mac(mac_or_serial))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                return self.async_create_entry(
                    title=radio.name or f"iNet Radio ({host})",
                    data={CONF_HOST: host},
                )
        finally:
            await manager.stop()

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            errors=errors,
        )

    async def _async_discover_radios(self) -> dict[str, str]:
        """Discover radios on the network using broadcast."""
        manager = RadioManager()
        discovered: dict[str, str] = {}
        discovery_event = asyncio.Event()

        def _on_discovery(radio: Any) -> None:
            discovered[radio.ip] = radio.name
            discovery_event.set()

        try:
            await manager.start()
            manager.register_discovery_callback(_on_discovery)
            await manager.discover()
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                await discovery_event.wait()
        except OSError, TimeoutError:
            _LOGGER.debug("Discovery failed or timed out", exc_info=True)
        finally:
            await manager.stop()

        return discovered
