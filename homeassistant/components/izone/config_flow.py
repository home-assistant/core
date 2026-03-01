"""Config flow for izone."""

import asyncio
from contextlib import suppress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DISPATCH_CONTROLLER_DISCOVERED, IZONE, TIMEOUT_DISCOVERY
from .discovery import (
    async_add_controller_by_ip,
    async_get_device_uid,
    async_start_discovery_service,
    async_stop_discovery_service,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
    }
)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Check if there are any iZone devices on the network via broadcast."""
    controller_ready = asyncio.Event()

    @callback
    def dispatch_discovered(_):
        controller_ready.set()

    async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, dispatch_discovered)

    disco = await async_start_discovery_service(hass)

    with suppress(TimeoutError):
        async with asyncio.timeout(TIMEOUT_DISCOVERY):
            await controller_ready.wait()

    if not disco.pi_disco.controllers:
        await async_stop_discovery_service(hass)
        _LOGGER.debug("No controllers found")
        return False

    _LOGGER.debug("Controllers %s", disco.pi_disco.controllers)
    return True


class IZoneConfigFlow(ConfigFlow, domain=IZONE):
    """Handle a config flow for iZone."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._device_uid: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        The user can either enter an IP address for a remote iZone hub,
        or leave it blank to use auto-discovery on the local network.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()

            if host:
                # Manual IP entry - try to connect
                try:
                    device_uid = await async_get_device_uid(self.hass, host)
                except ConnectionError:
                    errors[CONF_HOST] = "cannot_connect"
                else:
                    await self.async_set_unique_id(device_uid)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    self._host = host
                    self._device_uid = device_uid

                    # Initialize the controller
                    try:
                        await async_add_controller_by_ip(self.hass, host)
                    except ConnectionError:
                        errors[CONF_HOST] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title=f"iZone {device_uid}",
                            data={CONF_HOST: host},
                        )
            else:
                # Auto-discovery (blank host)
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle auto-discovery of iZone controllers on local network."""
        if user_input is not None:
            # User confirmed discovery
            return self.async_create_entry(
                title="iZone",
                data={},
            )

        has_devices = await _async_has_devices(self.hass)
        if not has_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="discover",
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        has_devices = await _async_has_devices(self.hass)
        if not has_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(
            title="iZone",
            data={},
        )
