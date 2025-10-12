"""Tests for Shelly cover platform."""

from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverState,
)
from homeassistant.components.shelly.const import RPC_COVER_UPDATE_TIME_SEC
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    init_integration,
    mock_polling_rpc_update,
    mutate_rpc_device_status,
    patch_platforms,
)

ROLLER_BLOCK_ID = 1


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.COVER]):
        yield


async def test_block_device_services(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block device cover services."""
    entity_id = "cover.test_name"
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSED

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-roller_0"


async def test_block_device_update(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 0)
    await init_integration(hass, 1)

    state = hass.states.get("cover.test_name")
    assert state
    assert state.state == CoverState.CLOSED

    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 100)
    mock_block_device.mock_update()
    state = hass.states.get("cover.test_name")
    assert state
    assert state.state == CoverState.OPEN


async def test_block_device_no_roller_blocks(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device without roller blocks."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "type", None)
    await init_integration(hass, 1)

    assert hass.states.get("cover.test_name") is None


async def test_rpc_device_services(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC device cover services."""
    entity_id = "cover.test_name_test_cover_0"
    await init_integration(hass, 2)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
        blocking=True,
    )

    mock_rpc_device.cover_set_position.assert_called_once_with(0, pos=50)
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "opening"
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_open.assert_called_once_with(0)
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.OPENING

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "closing"
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_close.assert_called_once_with(0)
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSING

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "closed")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_stop.assert_called_once_with(0)
    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSED

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cover:0"


async def test_rpc_device_no_cover_keys(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device without cover keys."""
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    await init_integration(hass, 2)

    assert hass.states.get("cover.test_name_test_cover_0") is None


async def test_rpc_device_update(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device update."""
    entity_id = "cover.test_name_test_cover_0"
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "closed")
    await init_integration(hass, 2)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "open")
    mock_rpc_device.mock_update()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN


async def test_rpc_device_no_position_control(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device with no position control."""
    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "pos_control", False
    )
    await init_integration(hass, 2)

    state = hass.states.get("cover.test_name_test_cover_0")
    assert state
    assert state.state == CoverState.OPEN


async def test_rpc_cover_tilt(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC cover that supports tilt."""
    entity_id = "cover.test_name_test_cover_0"

    config = deepcopy(mock_rpc_device.config)
    config["cover:0"]["slat"] = {"enable": True}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["cover:0"]["slat_pos"] = 0
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cover:0"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 50},
        blocking=True,
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "slat_pos", 50)
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_set_position.assert_called_once_with(0, slat_pos=50)
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    mock_rpc_device.cover_set_position.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "slat_pos", 100)
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_set_position.assert_called_once_with(0, slat_pos=100)
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    mock_rpc_device.cover_set_position.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "slat_pos", 10)
    mock_rpc_device.mock_update()

    mock_rpc_device.cover_stop.assert_called_once_with(0)
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 10


async def test_rpc_cover_position_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC update_position while the cover is moving."""
    entity_id = "cover.test_name_test_cover_0"
    await init_integration(hass, 2)

    # Set initial state to closing, position 50 set by cover_get_status mock
    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "closing"
    )
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    # Simulate position updates during closing
    for position in range(40, -1, -10):
        mock_rpc_device.cover_get_status.reset_mock()
        await mock_polling_rpc_update(hass, freezer, RPC_COVER_UPDATE_TIME_SEC)

        mock_rpc_device.cover_get_status.assert_called_once_with(0)
        assert (state := hass.states.get(entity_id))
        assert state.attributes[ATTR_CURRENT_POSITION] == position
        assert state.state == CoverState.CLOSING

    # Simulate cover reaching final position
    mock_rpc_device.cover_get_status.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "closed")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    assert state.state == CoverState.CLOSED

    # Ensure update_position does not call cover_get_status when the cover is not moving
    await mock_polling_rpc_update(hass, freezer, RPC_COVER_UPDATE_TIME_SEC)
    mock_rpc_device.cover_get_status.assert_not_called()


async def test_rpc_not_initialized_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update not called when device is not initialized."""
    entity_id = "cover.test_name_test_cover_0"
    await init_integration(hass, 2)

    # Set initial state to closing
    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "closing"
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "current_pos", 40)

    # mock device not initialized (e.g. disconnected)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    mock_rpc_device.mock_update()

    # wait for update interval to allow update_position to call cover_get_status
    await mock_polling_rpc_update(hass, freezer, RPC_COVER_UPDATE_TIME_SEC)

    mock_rpc_device.cover_get_status.assert_not_called()
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
