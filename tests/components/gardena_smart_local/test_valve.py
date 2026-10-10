"""Tests for the GARDENA smart local valve platform."""

from unittest.mock import AsyncMock, MagicMock

from gardena_smart_local_api.messages import Reply
import pytest

from homeassistant.components.gardena_smart_local.const import (
    DEFAULT_VALVE_DURATION_MINUTES,
)
from homeassistant.components.gardena_smart_local.valve import GardenaValve
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.exceptions import HomeAssistantError


def _mock_device(valve_ids: tuple[int, ...] = (0,), is_open: bool | None = False):
    device = MagicMock()
    device.id = "dev-1"
    device.serial_number = "00000001"
    device.software_version = "1.0.0"
    device.hardware_version = "1.0"
    device.model_definition.name = "Smart Water Control"
    device.model_definition.model_number = "1"
    device.valve_ids = list(valve_ids)
    device.is_valve_open.return_value = is_open
    device.build_open_valve_obj.return_value = "OPEN_OBJ"
    device.build_close_valve_obj.return_value = "CLOSE_OBJ"
    return device


@pytest.fixture
def coordinator() -> MagicMock:
    """Return a mock coordinator whose commands succeed."""
    coord = MagicMock()
    coord.connected = True
    coord.send_request = AsyncMock(return_value=[])
    return coord


def test_is_closed_inverts_is_valve_open(coordinator: MagicMock) -> None:
    """is_closed is the inverse of the device's is_valve_open."""
    device = _mock_device(is_open=True)
    coordinator.data = {device.id: device}
    valve = GardenaValve(coordinator, device, 0)

    assert valve.is_closed is False

    device.is_valve_open.return_value = False
    assert valve.is_closed is True

    device.is_valve_open.return_value = None
    assert valve.is_closed is None


def test_is_closed_none_when_device_unknown(coordinator: MagicMock) -> None:
    """is_closed is None while the device is not in the coordinator data."""
    device = _mock_device()
    coordinator.data = {}
    valve = GardenaValve(coordinator, device, 0)

    assert valve.is_closed is None


def test_naming_and_features(coordinator: MagicMock) -> None:
    """A single-valve device has no name; a multi-valve device is numbered."""
    single = GardenaValve(coordinator, _mock_device(valve_ids=(0,)), 0)
    assert single.name is None
    assert single.unique_id == "dev-1_valve_0"
    assert single.supported_features is (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )

    second = GardenaValve(coordinator, _mock_device(valve_ids=(0, 1)), 1)
    assert second.translation_key == "valve"
    assert second.translation_placeholders == {"number": "2"}


async def test_open_valve_uses_default_duration(coordinator: MagicMock) -> None:
    """Opening without a duration falls back to the fixed default."""
    device = _mock_device()
    coordinator.data = {device.id: device}
    valve = GardenaValve(coordinator, device, 0)

    await valve.async_open_valve()

    device.build_open_valve_obj.assert_called_once_with(
        0, DEFAULT_VALVE_DURATION_MINUTES * 60
    )
    coordinator.send_request.assert_awaited_once()


async def test_open_valve_for_custom_duration(coordinator: MagicMock) -> None:
    """open_valve passes the requested duration straight through."""
    device = _mock_device(valve_ids=(0, 1))
    coordinator.data = {device.id: device}
    valve = GardenaValve(coordinator, device, 1)

    await valve.async_open_valve_for(600)

    device.build_open_valve_obj.assert_called_once_with(1, 600)


async def test_close_valve(coordinator: MagicMock) -> None:
    """Closing builds the close command for the valve."""
    device = _mock_device()
    coordinator.data = {device.id: device}
    valve = GardenaValve(coordinator, device, 0)

    await valve.async_close_valve()

    device.build_close_valve_obj.assert_called_once_with(0)


async def test_rejected_command_raises(coordinator: MagicMock) -> None:
    """A negative reply from the gateway surfaces as an error."""
    device = _mock_device()
    coordinator.data = {device.id: device}
    coordinator.send_request = AsyncMock(
        return_value=[Reply(request_id="1", success=False)]
    )
    valve = GardenaValve(coordinator, device, 0)

    with pytest.raises(HomeAssistantError):
        await valve.async_close_valve()
