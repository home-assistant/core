"""Tests for EZVIZ select entities."""

from unittest.mock import AsyncMock

from pyezvizapi.constants import BatteryCameraWorkMode, DeviceCatagories, SupportExt
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .test_init import _mock_camera_data

from tests.common import MockConfigEntry

ENTITY_ID = "select.camera_1_battery_work_mode"


def _mock_battery_camera_data(work_mode: object) -> dict[str, object]:
    """Return a battery camera payload with the given work mode."""
    return _mock_camera_data(
        device_category=DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value,
        supportExt={str(SupportExt.SupportBatteryManage.value): "1"},
        battery_camera_work_mode=work_mode,
    )


@pytest.mark.parametrize(
    ("work_mode", "expected_state"),
    [
        (BatteryCameraWorkMode.HIGH_PERFORMANCE.value, "high_performance"),
        (BatteryCameraWorkMode.POWER_SAVE.value, "power_save"),
        ("PLUGGED_IN", "plugged_in"),
        (BatteryCameraWorkMode.ALWAYS_ON_VIDEO.value, STATE_UNKNOWN),
        (BatteryCameraWorkMode.UNKNOWN.value, STATE_UNKNOWN),
        (99, STATE_UNKNOWN),
    ],
)
async def test_battery_work_mode_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    work_mode: object,
    expected_state: str,
) -> None:
    """Test the battery work mode from numeric and legacy name payloads."""
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_battery_camera_data(work_mode)
    }

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_battery_work_mode_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test selecting a battery work mode sends its numeric value."""
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_battery_camera_data(BatteryCameraWorkMode.POWER_SAVE.value)
    }

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "high_performance"},
        blocking=True,
    )

    mock_ezviz_client.set_battery_camera_work_mode.assert_called_once_with(
        "C123456789", BatteryCameraWorkMode.HIGH_PERFORMANCE.value
    )
