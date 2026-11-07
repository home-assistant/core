"""Test Daikin Onecta setup."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from .conftest import FAKE_ACCESS_TOKEN

GATEWAY_DEVICES_URL = "https://api.onecta.daikineurope.com/v1/gateway-devices"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "issue_841_gateway_devices.json"


async def test_setup_with_gateway_missing_management_points(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up successfully when Daikin omits a gateway's management points."""
    gateway_devices = json.loads(FIXTURE_PATH.read_text())
    aioclient_mock.get(GATEWAY_DEVICES_URL, json=gateway_devices)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.coordinator."
            "OnectaDataUpdateCoordinator.async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.data) == 1
    device = config_entry.runtime_data.data["test-altherma-gateway"]
    assert device.available
    assert device.device.management_points == []
