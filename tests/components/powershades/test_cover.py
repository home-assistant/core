"""Tests for the PowerShades cover platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyowershades import (
    OP_JOG_STOP,
    OP_SET_POSITION,
    PowerShadesTimeoutError,
    build_packet,
    build_set_position_payload,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import push_status, setup_integration

ENTITY_ID = "cover.powershade_bedroom_shade"

pytestmark = pytest.mark.usefixtures("mock_powershades_connection")


async def test_cover_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cover entity."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("position", "expected_state"),
    [
        (0, CoverState.CLOSED),
        (100, CoverState.OPEN),
        (None, STATE_UNKNOWN),
    ],
)
async def test_cover_pushed_position(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
    position: int | None,
    expected_state: str,
) -> None:
    """A position pushed by the shade updates the cover state."""
    await setup_integration(hass, mock_config_entry)

    await push_status(hass, mock_powershades_connection, position)

    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("service", "service_data", "position", "expected_state"),
    [
        (SERVICE_OPEN_COVER, {}, 100, CoverState.OPENING),
        (SERVICE_CLOSE_COVER, {}, 0, CoverState.CLOSING),
        (SERVICE_SET_COVER_POSITION, {ATTR_POSITION: 30}, 30, CoverState.CLOSING),
    ],
)
async def test_move_cover(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, int],
    position: int,
    expected_state: str,
) -> None:
    """Moving the cover sends the position and shows it moving there."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_powershades_connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(position)
    )
    assert hass.states.get(ENTITY_ID).state == expected_state


async def test_move_cover_reaches_target(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The cover stops showing movement once it is within tolerance of the target."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    await push_status(hass, mock_powershades_connection, 80)
    assert hass.states.get(ENTITY_ID).state == CoverState.OPENING

    await push_status(hass, mock_powershades_connection, 99)
    assert hass.states.get(ENTITY_ID).state == CoverState.OPEN


async def test_move_cover_stuck(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A shade that doesn't move for 15 seconds stops showing movement."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == CoverState.CLOSING

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == CoverState.OPEN


async def test_move_cover_overridden_by_external_move(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A shade moving against the requested direction shows the new direction."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    await push_status(hass, mock_powershades_connection, 40)

    assert hass.states.get(ENTITY_ID).state == CoverState.CLOSING


async def test_external_move(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A move started outside HA is shown in the direction the shade moves."""
    await setup_integration(hass, mock_config_entry)

    await push_status(hass, mock_powershades_connection, 60)
    assert hass.states.get(ENTITY_ID).state == CoverState.OPENING

    await push_status(hass, mock_powershades_connection, 55)
    assert hass.states.get(ENTITY_ID).state == CoverState.CLOSING

    await push_status(hass, mock_powershades_connection, 0)
    assert hass.states.get(ENTITY_ID).state == CoverState.CLOSED


async def test_stop_cover(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Stopping the cover sends the jog stop command and clears the movement."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_powershades_connection.async_request.assert_any_call(OP_JOG_STOP, b"")
    assert hass.states.get(ENTITY_ID).state == CoverState.OPEN


async def test_move_cover_not_acknowledged(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A move the shade doesn't acknowledge raises and isn't shown as moving."""
    await setup_integration(hass, mock_config_entry)
    mock_powershades_connection.async_request.side_effect = PowerShadesTimeoutError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert exc_info.value.translation_key == "command_not_acknowledged"
    assert hass.states.get(ENTITY_ID).state == CoverState.OPEN


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (PowerShadesTimeoutError, None),
        (None, build_packet(0x00)),
    ],
    ids=["timeout", "malformed_reply"],
)
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    return_value: bytes | None,
) -> None:
    """The cover becomes unavailable when polling the shade fails."""
    await setup_integration(hass, mock_config_entry)
    mock_powershades_connection.async_request.side_effect = side_effect
    mock_powershades_connection.async_request.return_value = return_value

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
