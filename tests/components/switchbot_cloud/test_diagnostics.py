"""Tests for the SwitchBot Cloud diagnostics."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from switchbot_api import Device, PowerState, Remote
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

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


@pytest.mark.usefixtures(
    "mock_get_webook_configuration", "mock_delete_webhook", "mock_setup_webhook"
)
@pytest.mark.parametrize(
    ("core_config", "webhook_registered"),
    [
        pytest.param({"external_url": "https://example.com"}, True, id="external_url"),
        pytest.param({}, False, id="no_external_url"),
    ],
)
async def test_diagnostics_webhook_registered(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    core_config: dict[str, Any],
    webhook_registered: bool,
) -> None:
    """Test diagnostics only report the webhook as registered when it is."""
    await async_process_ha_core_config(hass, core_config)
    mock_list_devices.return_value = [
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}
    entry = await configure_integration(hass)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["webhook_registered"] is webhook_registered
