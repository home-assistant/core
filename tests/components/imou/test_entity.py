"""Tests for Imou base entity helpers."""

from unittest.mock import AsyncMock

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest

from homeassistant.components.imou.const import (
    DOMAIN,
    PARAM_MUTE,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.components.imou.entity import imou_device_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def _online_device_with_channel() -> ImouHaDevice:
    """Single online device with a channel (matches identifier unit-test scenario)."""
    device = ImouHaDevice("dev-1", "Cam", "Imou", "m1", "1.0")
    device.set_channel_id("ch9")
    device._buttons[PARAM_MUTE] = {}
    device._sensors[PARAM_STATUS] = {PARAM_STATE: DeviceStatus.ONLINE.value}
    return device


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
    "imou_mock_devices",
    [[_online_device_with_channel()]],
    indirect=True,
)
async def test_imou_device_identifier_via_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Device registry uses the same identifier as imou_device_identifier (integration path)."""
    ref = _online_device_with_channel()
    expected_key = imou_device_identifier(ref)

    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert len(devices) == 1
    assert (DOMAIN, expected_key) in devices[0].identifiers
