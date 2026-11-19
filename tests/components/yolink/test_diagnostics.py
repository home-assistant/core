"""Tests for the YoLink diagnostics."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from yolink.client import YoLinkClient
from yolink.const import ATTR_DEVICE_TH_SENSOR, ATTR_DEVICE_WATER_METER_CONTROLLER
from yolink.device import YoLinkDevice, YoLinkDeviceMode
from yolink.exception import YoLinkClientError
from yolink.model import BRDP

from homeassistant.components.yolink.const import DEV_MODEL_WATER_METER_YS5018_UC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


def _mock_device(
    *,
    device_id: str,
    device_name: str,
    device_type: str,
    device_model: str,
    execute: AsyncMock,
) -> YoLinkDevice:
    """Create a YoLink device with a mocked API client."""
    client = MagicMock(spec=YoLinkClient)
    client.execute = execute
    return YoLinkDevice(
        YoLinkDeviceMode(
            deviceId=device_id,
            name=device_name,
            token="secret-device-token",
            type=device_type,
            modelName=device_model,
        ),
        client,
    )


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    water_meter_report: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    state = deepcopy(water_meter_report["data"])
    state["deviceId"] = "d88b4c0100000001"
    state["loraInfo"]["netId"] = "010203"
    state["loraInfo"]["gatewayId"] = "d88b4c1600000002"
    water_meter = _mock_device(
        device_id="d88b4c0100000001",
        device_name="Kitchen water meter",
        device_type=ATTR_DEVICE_WATER_METER_CONTROLLER,
        device_model=DEV_MODEL_WATER_METER_YS5018_UC,
        execute=AsyncMock(
            return_value=BRDP(
                code="000000",
                desc="Success",
                data={"state": state, "deviceId": "d88b4c0100000001"},
            )
        ),
    )
    # A device that fails its first refresh keeps an empty state.
    th_sensor = _mock_device(
        device_id="d88b4c0100000003",
        device_name="Bedroom sensor",
        device_type=ATTR_DEVICE_TH_SENSOR,
        device_model="YS8003-UC",
        execute=AsyncMock(side_effect=YoLinkClientError("000201", "Offline")),
    )
    mock_yolink_home.return_value.get_devices.return_value = [water_meter, th_sensor]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
