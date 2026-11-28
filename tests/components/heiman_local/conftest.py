"""Fixtures for Heiman Local tests."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from homeassistant.components.heiman_local.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@dataclass
class WiFiSwitch:
    """Minimal HTTP fixture for the first supported device."""

    address: dict[str, str | int] = field(default_factory=dict)
    schema: str = "heiman_wifi_v1"
    mac: str = "A8:C1:D6:01:02:03"
    power: bool = False
    online: bool = True
    reject_command: bool = False
    apply_command: bool = True
    flat_state: bool = False
    received: list[dict[str, bool | str]] = field(default_factory=list)

    async def info(self, request: web.Request) -> web.Response:
        """Report switch identity."""
        return web.json_response(
            {
                "schema": self.schema,
                "mac": self.mac,
                "deviceType": "SW",
                "deviceName": "Heiman WiFi Switch",
                "model": "LAN-SW",
                "firmwareVersion": "1.0.0",
            }
        )

    async def state(self, request: web.Request) -> web.Response:
        """Report the actual switch state."""
        if not self.online:
            raise web.HTTPServiceUnavailable
        if self.flat_state:
            return web.json_response({"properties": {"power": self.power}})
        return web.json_response(
            {"devices": [{"id": self.mac, "properties": {"power": self.power}}]}
        )

    async def control(self, request: web.Request) -> web.Response:
        """Receive an explicit power command."""
        payload = await request.json()
        self.received.append(payload)
        if self.reject_command:
            return web.json_response({"ok": False})
        if self.apply_command:
            self.power = payload["value"]
        return web.json_response({"ok": True})


@pytest.fixture
async def device(socket_enabled: None) -> AsyncIterator[WiFiSwitch]:
    """Start a loopback HTTP switch."""
    switch = WiFiSwitch()
    app = web.Application()
    app.router.add_get("/info", switch.info)
    app.router.add_get("/state", switch.state)
    app.router.add_post("/control", switch.control)
    async with TestServer(app) as server:
        switch.address = {CONF_HOST: server.host, CONF_PORT: server.port}
        yield switch


@pytest.fixture
async def entry(hass: HomeAssistant, device: WiFiSwitch) -> ConfigEntry:
    """Add the switch through the real config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], device.address
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]
