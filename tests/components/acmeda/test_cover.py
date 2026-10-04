"""Tests for the Acmeda cover module."""

from unittest.mock import AsyncMock, MagicMock

import aiopulse
import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("closed_percent", "expected_position"),
    [
        (50, 50),
        (100, 0),
        (0, 100),
        (None, None),
    ],
)
async def test_cover_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    closed_percent: int | None,
    expected_position: int | None,
) -> None:
    """Test cover position is reported correctly."""
    mock_roller.closed_percent = closed_percent
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    state = hass.states.get("cover.roller")
    assert state is not None
    if expected_position is None:
        assert state.attributes.get(ATTR_CURRENT_POSITION) is None
    else:
        assert state.attributes[ATTR_CURRENT_POSITION] == expected_position


@pytest.mark.parametrize(
    ("closed_percent", "expected_position"),
    [
        (50, 50),
        (100, 0),
        (0, 100),
        (None, None),
    ],
)
async def test_cover_tilt_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    closed_percent: int | None,
    expected_position: int | None,
) -> None:
    """Test cover tilt position is reported correctly."""
    mock_roller.closed_percent = closed_percent
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    state = hass.states.get("cover.roller")
    assert state is not None
    if expected_position is None:
        assert state.attributes.get(ATTR_CURRENT_TILT_POSITION) is None
    else:
        assert state.attributes[ATTR_CURRENT_TILT_POSITION] == expected_position


@pytest.mark.parametrize(
    ("roller_type", "expected_features"),
    [
        (
            1,
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION,
        ),
        (
            7,
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
        (
            10,
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    roller_type: int,
    expected_features: CoverEntityFeature,
) -> None:
    """Test supported_features for different roller types."""
    mock_roller.type = roller_type
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    state = hass.states.get("cover.roller")
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected_features


@pytest.mark.parametrize(
    ("closed_percent", "expected_state"),
    [
        (100, CoverState.CLOSED),
        (0, CoverState.OPEN),
        (50, CoverState.OPEN),
        (None, STATE_UNKNOWN),
    ],
)
async def test_cover_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    closed_percent: int | None,
    expected_state: str,
) -> None:
    """Test cover state is reported correctly."""
    mock_roller.closed_percent = closed_percent
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    state = hass.states.get("cover.roller")
    assert state is not None
    assert state.state == expected_state


async def test_cover_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test cover services call correct roller methods."""
    mock_roller.move_down = AsyncMock()
    mock_roller.move_up = AsyncMock()
    mock_roller.move_stop = AsyncMock()
    mock_roller.move_to = AsyncMock()
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    entity_id = "cover.roller"
    await hass.services.async_call(
        COVER_DOMAIN, "close_cover", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_down.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN, "open_cover", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_up.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN, "stop_cover", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_stop.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN,
        "set_cover_position",
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 75},
        blocking=True,
    )
    mock_roller.move_to.assert_called_once_with(25)


async def test_cover_tilt_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test cover tilt services call correct roller methods."""
    mock_roller.type = 7
    mock_roller.move_down = AsyncMock()
    mock_roller.move_up = AsyncMock()
    mock_roller.move_stop = AsyncMock()
    mock_roller.move_to = AsyncMock()
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    entity_id = "cover.roller"
    await hass.services.async_call(
        COVER_DOMAIN, "close_cover_tilt", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_down.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN, "open_cover_tilt", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_up.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN, "stop_cover_tilt", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_roller.move_stop.assert_called_once()

    await hass.services.async_call(
        COVER_DOMAIN,
        "set_cover_tilt_position",
        {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 75},
        blocking=True,
    )
    mock_roller.move_to.assert_called_once_with(25)


async def test_entity_registration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entity is registered with correct device info."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    # Verify entity registration
    entity = entity_registry.async_get("cover.roller")
    assert entity is not None
    assert entity.unique_id == str(mock_roller.id)

    # Verify device_id property on entity instance
    cover_entity = hass.data[COVER_DOMAIN].get_entity("cover.roller")
    assert cover_entity is not None
    assert cover_entity.device_id == str(mock_roller.id)

    # Verify device info
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_roller.id)), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Rollease Acmeda"
    assert device.name == mock_roller.name


async def test_entity_notify_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test entity subscribes to roller callback and updates state."""
    mock_roller.closed_percent = 50
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    # Verify entity state reflects roller position
    state = hass.states.get("cover.roller")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    # Verify entity subscribed to the roller's callback
    mock_roller.callback_subscribe.assert_called()

    # Verify state updates when roller position changes
    mock_roller.closed_percent = 75
    cover_entity = hass.data[COVER_DOMAIN].get_entity("cover.roller")
    assert cover_entity is not None
    cover_entity.async_write_ha_state()

    state = hass.states.get("cover.roller")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 25
