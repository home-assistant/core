"""Tests for Imou base entity helpers."""

from unittest.mock import AsyncMock, MagicMock

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest

from homeassistant.components.imou.button import ImouButton
from homeassistant.components.imou.const import PARAM_MUTE, PARAM_STATE, PARAM_STATUS
from homeassistant.components.imou.coordinator import ImouDataUpdateCoordinator
from homeassistant.components.imou.entity import imou_device_identifier


@pytest.mark.parametrize(
    ("set_channel", "expected_id"),
    [
        (False, "dev-1"),
        (True, "dev-1_ch9"),
    ],
)
def test_imou_device_identifier(
    set_channel: bool,
    expected_id: str,
) -> None:
    """Test registry identifier uses channel when present."""
    device = ImouHaDevice("dev-1", "Cam", "Imou", "model-x", "2.0")
    if set_channel:
        device.set_channel_id("ch9")
    assert imou_device_identifier(device) == expected_id


@pytest.mark.parametrize(
    ("last_ok", "has_status_sensor", "state_value", "expected"),
    [
        (True, True, DeviceStatus.ONLINE.value, True),
        (True, True, DeviceStatus.OFFLINE.value, False),
        (False, True, DeviceStatus.ONLINE.value, False),
        (True, False, DeviceStatus.ONLINE.value, False),
    ],
)
@pytest.mark.usefixtures("hass")
def test_imou_entity_available(
    last_ok: bool,
    has_status_sensor: bool,
    state_value: str,
    expected: bool,
) -> None:
    """Test availability combines coordinator success and device status."""
    device = ImouHaDevice("d1", "n", "m", "md", "1")
    if has_status_sensor:
        device._sensors[PARAM_STATUS] = {PARAM_STATE: state_value}
    else:
        del device._sensors[PARAM_STATUS]

    coordinator = MagicMock(spec=ImouDataUpdateCoordinator)
    coordinator.last_update_success = last_ok
    coordinator.device_manager = MagicMock()
    coordinator.device_manager.async_press_button = AsyncMock()

    entity = ImouButton(coordinator, PARAM_MUTE, device)
    assert entity.available is expected
