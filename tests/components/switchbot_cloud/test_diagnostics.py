"""Tests for the SwitchBot Cloud diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from switchbot_api import Remote
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import AIR_PURIFIER_INFO, configure_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    mock_list_devices.return_value = [
        AIR_PURIFIER_INFO,
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="DIY Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = await async_load_json_object_fixture(
        hass, "air_purifier_status.json", DOMAIN
    )
    entry = await configure_integration(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
