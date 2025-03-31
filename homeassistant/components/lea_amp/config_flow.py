"""Config flow for LEA Amp local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_flow

from .const import CONNECTION_TIMEOUT, DOMAIN, LEA_IP, PORT
from .controller import LeaController

_LOGGER = logging.getLogger(__name__)


class ExampleConfigFlow(data_entry_flow.FlowHandler):
    """Handle a config flow."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Step User."""
        # Specify items in the order they are to be displayed in the UI
        data_schema = {
            vol.Required("ip_address"): str,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(data_schema))


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    # adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)

    controller: LeaController = LeaController(
        loop=hass.loop,
        port=PORT,
        ip_address=LEA_IP,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    try:
        await controller.start()
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    try:
        async with asyncio.timeout(delay=CONNECTION_TIMEOUT):
            while not controller.zones:
                await asyncio.sleep(delay=1)
    except TimeoutError:
        _LOGGER.debug("HELLO No devices found")

    devices_count = len(controller.zones)
    cleanup_complete: asyncio.Event = controller.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(cleanup_complete.wait(), 1)

    return devices_count > 0


config_entry_flow.register_discovery_flow(DOMAIN, "LEA AMP local", _async_has_devices)
