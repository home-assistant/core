"""Shared fixtures for LANBON LOIP tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiolanbon.models import DeviceSnapshot, GatewayInfo
import pytest

from homeassistant.components.lanbon.const import CONF_GATEWAY_ID, CONF_SCHEME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.0.111"
PORT = 8765
TOKEN = "a" * 32
GATEWAY_ID = "dcda0c3bc714"

INFO: dict[str, Any] = {
    "protocol": "loip",
    "protocol_version": "1.0.0",
    "gateway_id": GATEWAY_ID,
    "manufacturer": "LANBON",
    "series": "L10",
    "model": "L10-4G",
    "firmware_version": "1.0.0",
    "api_enabled": True,
    "transports": {"http": True, "events": "polling"},
    "limits": {},
}

SNAPSHOT: dict[str, Any] = {
    "protocol_version": "1.0.0",
    "gateway_id": GATEWAY_ID,
    "revision": "1",
    "devices": [
        {
            "id": GATEWAY_ID,
            "name": "L10-4G",
            "manufacturer": "LANBON",
            "series": "L10",
            "model": "L10-4G",
            "online": True,
            "role": "gateway",
            "components": [
                {
                    "id": "switch:1",
                    "type": "switch",
                    "name": "Light1",
                    "enabled": True,
                    "features": ["on_off"],
                    "commands": ["set_on"],
                    "state": {"on": False},
                    "constraints": {},
                },
                {
                    "id": "light:1",
                    "type": "light",
                    "name": "Dimmer",
                    "enabled": True,
                    "features": ["on_off", "brightness"],
                    "commands": ["set_on", "set_brightness"],
                    "state": {"on": True, "brightness": 50},
                    "constraints": {},
                },
            ],
        }
    ],
}


def gateway_info(**overrides: Any) -> GatewayInfo:
    """Return GatewayInfo for tests."""
    data = {**INFO, **overrides}
    if "transports" in overrides or "limits" in overrides:
        data = {**INFO, **overrides}
    return GatewayInfo.from_dict(data)


def snapshot() -> DeviceSnapshot:
    """Return a DeviceSnapshot with one switch and one ignored light."""
    return DeviceSnapshot.from_dict(SNAPSHOT)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_ID,
        title="L10-4G",
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_TOKEN: TOKEN,
            CONF_SCHEME: "http",
            CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )


@pytest.fixture
def mock_lanbon_client() -> Generator[MagicMock]:
    """Mock aiolanbon client methods used during setup and control."""
    info = gateway_info()
    snap = snapshot()
    with (
        patch(
            "homeassistant.components.lanbon.config_flow.LanbonClient.get_info",
            new_callable=AsyncMock,
            return_value=info,
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            new_callable=AsyncMock,
            return_value=info,
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_devices",
            new_callable=AsyncMock,
            return_value=snap,
        ) as mock_devices,
        patch(
            "homeassistant.components.lanbon.LanbonClient.send_command",
            new_callable=AsyncMock,
        ) as mock_command,
    ):
        mock = MagicMock()
        mock.get_devices = mock_devices
        mock.send_command = mock_command
        yield mock


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: MagicMock,
) -> MockConfigEntry:
    """Set up the LANBON integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
