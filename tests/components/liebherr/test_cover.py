"""Test the Liebherr cover platform."""

import copy
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    AutoDoorControl,
    Device,
    DeviceState,
    DeviceType,
    DoorState,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import LiebherrConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "cover.test_fridge_top_zone_autodoor"


def _mock_door_state(door_state: DoorState | None) -> DeviceState:
    """Create a DeviceState with a single AutoDoorControl."""
    return DeviceState(
        device=MOCK_DEVICE,
        controls=[
            AutoDoorControl(
                name="autodoor",
                type="AutoDoorControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                value=door_state,
            ),
        ],
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.COVER]


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("init_integration")
async def test_covers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all cover entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_cover_state_closed(
    hass: HomeAssistant,
) -> None:
    """Test cover entity reports closed state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    ("door_state", "expected_state"),
    [
        (DoorState.OPEN, STATE_OPEN),
        (DoorState.MOVING, STATE_OPEN),
        (None, "unknown"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_cover_state_after_poll(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    door_state: DoorState | None,
    expected_state: str,
) -> None:
    """Test cover state after polling different door states."""
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: (
        _mock_door_state(door_state)
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "door_state", "expected_state", "expected_value"),
    [
        (SERVICE_OPEN_COVER, DoorState.OPEN, STATE_OPEN, True),
        (SERVICE_CLOSE_COVER, DoorState.CLOSED, STATE_CLOSED, False),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_cover_service_calls(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    service: str,
    door_state: DoorState,
    expected_state: str,
    expected_value: bool,
) -> None:
    """Test cover open/close service calls settle to expected state."""
    initial_call_count = mock_liebherr_client.get_device_state.call_count

    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: (
        _mock_door_state(door_state)
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_liebherr_client.trigger_auto_door.assert_called_once_with(
        device_id="test_device_id",
        zone_id=1,
        value=expected_value,
    )

    # Verify coordinator refresh was triggered
    assert mock_liebherr_client.get_device_state.call_count > initial_call_count

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
async def test_cover_state_settles_after_poll(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test door state settles correctly across command and subsequent poll."""
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: (
        _mock_door_state(DoorState.OPEN)
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OPEN

    # Door closes on next scheduled poll
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: (
        _mock_door_state(DoorState.CLOSED)
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    "service",
    [SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER],
    ids=["open", "close"],
)
@pytest.mark.usefixtures("init_integration")
async def test_cover_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    service: str,
) -> None:
    """Test cover fails gracefully on connection error and resets optimistic state."""
    mock_liebherr_client.trigger_auto_door.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the device",
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    # Optimistic state should be cleared after failure
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_CLOSED


@pytest.mark.usefixtures("init_integration")
async def test_cover_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover entity behavior when auto door control is removed."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_CLOSED

    # Device stops reporting auto door control
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_no_cover_entity_without_control(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test no cover entity created when device has no auto door control."""
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None


async def test_single_zone_cover(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test single zone device uses name without zone suffix."""
    device = Device(
        device_id="single_zone_id",
        nickname="Single Zone Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=5,
                target=4,
                min=2,
                max=8,
                unit=TemperatureUnit.CELSIUS,
            ),
            AutoDoorControl(
                name="autodoor",
                type="AutoDoorControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                value=DoorState.CLOSED,
            ),
        ],
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Single zone device should not have zone suffix
    entity_id = "cover.single_zone_fridge_autodoor"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED


async def test_dynamic_device_discovery(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices with auto door are automatically discovered."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get("cover.new_fridge_autodoor") is None

    new_device = Device(
        device_id="new_device_id",
        nickname="New Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    new_device_state = DeviceState(
        device=new_device,
        controls=[
            AutoDoorControl(
                name="autodoor",
                type="AutoDoorControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                value=DoorState.CLOSED,
            ),
        ],
    )

    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, new_device]
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(
            new_device_state if device_id == "new_device_id" else MOCK_DEVICE_STATE
        )
    )

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("cover.new_fridge_autodoor")
    assert state is not None
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_OPEN_COVER, STATE_OPENING),
        (SERVICE_CLOSE_COVER, STATE_CLOSING),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_cover_optimistic_state(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    service: str,
    expected_state: str,
) -> None:
    """Test optimistic opening/closing state is set before command completes."""
    states: list[str] = []

    # Block the API call so we can observe intermediate state
    async def _delayed_trigger(**kwargs: object) -> None:
        states.append(hass.states.get(ENTITY_ID).state)  # type: ignore[union-attr]

    mock_liebherr_client.trigger_auto_door.side_effect = _delayed_trigger

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert expected_state in states
