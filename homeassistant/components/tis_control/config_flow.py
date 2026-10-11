"""Config flow for TIS Control."""

import asyncio
import logging
from typing import Any, override

import probatio
from tis_smartbus import (
    DEFAULT_PORT,
    Category,
    DiscoveredDevice,
    TISConnectionError,
    TISGateway,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT

from .const import DISCOVERY_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


async def _async_find_channels(gateway: TISGateway) -> list[dict[str, Any]]:
    """Find the dimmer modules on the bus and list their channels (read-only)."""
    found = await gateway.discover(DISCOVERY_TIMEOUT)
    dimmers = [m for m in found if m.device_type.category is Category.DIMMER]
    # The module itself knows how many channels it has; the device table is the fallback.
    replies = await asyncio.gather(
        *(gateway.read_channels(m.subnet, m.device) for m in dimmers)
    )
    channels: list[dict[str, Any]] = []
    for module, levels in zip(dimmers, replies, strict=True):
        count = len(levels) if levels else module.device_type.channels
        channels.extend(_channel(module, channel) for channel in range(1, count + 1))
    return channels


def _channel(module: DiscoveredDevice, channel: int) -> dict[str, Any]:
    model = module.device_type.model
    return {
        "subnet": module.subnet,
        "device": module.device,
        "channel": channel,
        "module": module.name or f"{model} {module.subnet}.{module.device}",
        "model": model,
    }


class TISConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TIS Control."""

    VERSION = 1

    def _site_already_configured(self, channels: list[dict[str, Any]]) -> bool:
        """Return True if an existing entry already has any of these modules."""
        found = {(c["subnet"], c["device"]) for c in channels}
        return any(
            found & {(d["subnet"], d["device"]) for d in entry.data[CONF_DEVICES]}
            for entry in self._async_current_entries(include_ignore=False)
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a gateway, then find the dimmers behind every gateway on the network."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            gateway = TISGateway(host, port)
            channels: list[dict[str, Any]] = []
            try:
                await gateway.connect()
                channels = await _async_find_channels(gateway)
            except TISConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await gateway.close()
            if not errors and not channels:
                errors["base"] = "no_devices"
            if not errors and self._site_already_configured(channels):
                # Every gateway of a site reaches the same modules: one entry covers them all.
                return self.async_abort(reason="already_configured")
            if not errors:
                return self.async_create_entry(
                    title=f"TIS gateway {host}",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_DEVICES: channels},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
