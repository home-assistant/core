"""Tests for Shelly fan platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, mutate_rpc_device_status, patch_platforms

ENTITY_ID = f"{FAN_DOMAIN}.test_name"


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.FAN]):
        yield


@pytest.fixture
def mock_fan_device(mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Add a fan component to the mocked RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["fan:0"] = {"id": 0, "name": None}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["fan:0"] = {"id": 0, "mode": "manual", "on": False, "speed": 14}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    return mock_rpc_device


@pytest.mark.usefixtures("mock_fan_device")
async def test_rpc_fan(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test RPC fan entity."""
    await init_integration(hass, 2)

    assert (state := hass.states.get(ENTITY_ID))
    assert state == snapshot(name=f"{ENTITY_ID}-state")

    assert (entry := entity_registry.async_get(ENTITY_ID))
    assert entry == snapshot(name=f"{ENTITY_ID}-entry")


@pytest.mark.parametrize(
    (
        "mode",
        "is_on",
        "speed",
        "expected_state",
        "expected_percentage",
        "expected_preset",
    ),
    [
        ("manual", False, 14, STATE_OFF, 0, None),
        ("manual", True, 50, STATE_ON, 50, None),
        ("auto", True, 70, STATE_ON, 70, "auto"),
        ("auto", False, 70, STATE_OFF, 0, "auto"),
    ],
)
async def test_rpc_fan_state(
    hass: HomeAssistant,
    mock_fan_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    is_on: bool,
    speed: int,
    expected_state: str,
    expected_percentage: int,
    expected_preset: str | None,
) -> None:
    """Test RPC fan state."""
    await init_integration(hass, 2)

    mutate_rpc_device_status(monkeypatch, mock_fan_device, "fan:0", "mode", mode)
    mutate_rpc_device_status(monkeypatch, mock_fan_device, "fan:0", "on", is_on)
    mutate_rpc_device_status(monkeypatch, mock_fan_device, "fan:0", "speed", speed)
    mock_fan_device.mock_update()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected_state
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset


@pytest.mark.parametrize(
    ("service", "service_data", "expected_params"),
    [
        (SERVICE_TURN_ON, {}, {"id": 0, "mode": "manual", "on": True}),
        (
            SERVICE_TURN_ON,
            {ATTR_PERCENTAGE: 30},
            {"id": 0, "mode": "manual", "on": True, "speed": 30},
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PERCENTAGE: 0},
            {"id": 0, "mode": "manual", "on": False},
        ),
        (SERVICE_TURN_ON, {ATTR_PRESET_MODE: "auto"}, {"id": 0, "mode": "auto"}),
        (SERVICE_TURN_OFF, {}, {"id": 0, "mode": "manual", "on": False}),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 80},
            {"id": 0, "mode": "manual", "on": True, "speed": 80},
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 0},
            {"id": 0, "mode": "manual", "on": False},
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "auto"},
            {"id": 0, "mode": "auto"},
        ),
    ],
)
async def test_rpc_fan_services(
    hass: HomeAssistant,
    mock_fan_device: Mock,
    service: str,
    service_data: dict[str, Any],
    expected_params: dict[str, Any],
) -> None:
    """Test RPC fan services."""
    await init_integration(hass, 2)

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_fan_device.call_rpc.assert_called_once_with("Fan.Set", expected_params)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            f"Device communication error occurred while calling action for {ENTITY_ID} of Test name",
        ),
        (
            RpcCallError(999),
            f"RPC call error occurred while calling action for {ENTITY_ID} of Test name",
        ),
    ],
)
async def test_rpc_fan_exc(
    hass: HomeAssistant,
    mock_fan_device: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test RPC fan with exception."""
    await init_integration(hass, 2)

    mock_fan_device.call_rpc.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_block_device")
async def test_block_device_no_fan(hass: HomeAssistant) -> None:
    """Test that block devices do not create fan entities."""
    await init_integration(hass, 1)

    assert hass.states.async_entity_ids(FAN_DOMAIN) == []
