"""Tests for the EZVIZ diagnostics."""

from unittest.mock import AsyncMock

from pyezvizapi.constants import DeviceCatagories, SupportExt
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .test_init import _mock_camera_data


@pytest.mark.parametrize(
    "config_entry_fixture", ["mock_config_entry", "mock_camera_config_entry"]
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_ezviz_client: AsyncMock,
    request: pytest.FixtureRequest,
    config_entry_fixture: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_camera_data(
            device_category=DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value,
            supportExt={str(SupportExt.SupportBatteryManage.value): "1"},
            switches={7: True, 21: False},
            battery_level=85,
            battery_camera_work_mode=1,
            alarm_sound_mod="SOFT",
            last_alarm_time="2023-01-01T12:00:00Z",
            last_alarm_pic="https://example.com/image.jpg",
            last_alarm_type_code="2701",
            last_alarm_type_name="Motion Detected",
            wan_ip="203.0.113.1",
            serial="C123456789",
            encrypted_pwd_hash="hash",
        )
    }
    config_entry: MockConfigEntry = request.getfixturevalue(config_entry_fixture)
    await setup_integration(hass, config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
