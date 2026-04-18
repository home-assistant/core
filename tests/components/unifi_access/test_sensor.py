"""Tests for the UniFi Access sensor platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from unifi_access_api import (
    ApiConnectionError,
    ApiNotFoundError,
    DoorLockRuleStatus,
    DoorLockRuleType,
    DoorPositionStatus,
)
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateState,
    LocationUpdateV2,
    WebsocketMessage,
    WsDoorLockRuleStatus,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_LOCK_RULE_ENTITY = "sensor.front_door_lock_rule"
FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY = "sensor.front_door_rule_end_time"
BACK_DOOR_LOCK_RULE_ENTITY = "sensor.back_door_lock_rule"
BACK_DOOR_LOCK_RULE_END_TIME_ENTITY = "sensor.back_door_rule_end_time"


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities are created with expected state."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(
            type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
        )
    )
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_lock_rule_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test sensor states reflect lock rule values."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(
            type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
        )
    )
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "keep_lock"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == (
        datetime.fromtimestamp(1700000000, tz=UTC).isoformat()
    )


async def test_sensor_no_active_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test sensor state is unknown when no lock rule is active."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == "unknown"


async def test_sensor_not_created_when_lock_rules_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that sensor entities are not created when lock rules are unsupported."""
    mock_client.get_door_lock_rule = AsyncMock(side_effect=ApiNotFoundError())
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY) is None
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY) is None


async def test_sensor_created_for_supported_doors_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test lock rule sensors are created only for doors that support them."""

    async def mock_get_door_lock_rule(door_id: str) -> DoorLockRuleStatus:
        if door_id == "door-001":
            return DoorLockRuleStatus(
                type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
            )
        raise ApiNotFoundError

    mock_client.get_door_lock_rule = AsyncMock(side_effect=mock_get_door_lock_rule)

    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY) is not None
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY) is not None
    assert hass.states.get(BACK_DOOR_LOCK_RULE_ENTITY) is None
    assert hass.states.get(BACK_DOOR_LOCK_RULE_END_TIME_ENTITY) is None


async def test_sensor_created_after_websocket_update_when_initial_fetch_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test websocket updates refine placeholder sensors after a transient startup error."""
    mock_client.get_door_lock_rule = AsyncMock(
        side_effect=ApiConnectionError("Connection failed")
    )

    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == "unknown"
    assert hass.states.get(BACK_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(BACK_DOOR_LOCK_RULE_END_TIME_ENTITY).state == "unknown"

    handlers = _get_ws_handlers(mock_client)
    update_msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState(
                remain_lock=WsDoorLockRuleStatus(
                    type=DoorLockRuleType.KEEP_LOCK,
                    until=1700000000,
                )
            ),
        ),
    )
    await handlers["access.data.device.location_update_v2"](update_msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "keep_lock"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == (
        datetime.fromtimestamp(1700000000, tz=UTC).isoformat()
    )
    assert hass.states.get(BACK_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(BACK_DOOR_LOCK_RULE_END_TIME_ENTITY).state == "unknown"


async def test_sensor_placeholder_created_only_for_transient_error_doors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test placeholders are created only for doors with transient fetch errors."""

    async def mock_get_door_lock_rule(door_id: str) -> DoorLockRuleStatus:
        if door_id == "door-001":
            raise ApiConnectionError("Connection failed")
        raise ApiNotFoundError

    mock_client.get_door_lock_rule = AsyncMock(side_effect=mock_get_door_lock_rule)

    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY) is not None
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY) is not None
    assert hass.states.get(BACK_DOOR_LOCK_RULE_ENTITY) is None
    assert hass.states.get(BACK_DOOR_LOCK_RULE_END_TIME_ENTITY) is None


async def test_sensor_lock_rule_websocket_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test lock rule sensor updates via websocket."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "unknown"

    handlers = _get_ws_handlers(mock_client)
    update_msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState(
                remain_lock=WsDoorLockRuleStatus(
                    type=DoorLockRuleType.KEEP_LOCK,
                    until=1700000000,
                )
            ),
        ),
    )
    await handlers["access.data.device.location_update_v2"](update_msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "keep_lock"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == (
        datetime.fromtimestamp(1700000000, tz=UTC).isoformat()
    )


async def test_sensor_lock_rule_websocket_rule_cleared(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test lock rule sensor clears when websocket reports no active rule."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(
            type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
        )
    )
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "keep_lock"

    handlers = _get_ws_handlers(mock_client)
    update_msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState.model_validate({"remain_lock": None}),
        ),
    )
    await handlers["access.data.device.location_update_v2"](update_msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "unknown"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == "unknown"


async def test_sensor_partial_websocket_update_preserves_lock_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a partial websocket update keeps the current lock rule state."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(
            type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
        )
    )
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    handlers = _get_ws_handlers(mock_client)
    update_msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState(dps=DoorPositionStatus.OPEN),
        ),
    )
    await handlers["access.data.device.location_update_v2"](update_msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_ENTITY).state == "keep_lock"
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_END_TIME_ENTITY).state == (
        datetime.fromtimestamp(1700000000, tz=UTC).isoformat()
    )
