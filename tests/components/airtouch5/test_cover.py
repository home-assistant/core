"""Tests for the Airtouch5 cover platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from airtouch5py.packets.zone_status import (
    ControlMethod,
    ZonePowerState,
    ZoneStatusZone,
)
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

COVER_ENTITY_ID = "cover.zone_1_damper"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.airtouch5.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_actions(
    hass: HomeAssistant,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the actions of the Airtouch5 covers."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    mock_airtouch5_client.send_packet.assert_called_once()
    mock_airtouch5_client.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )
    mock_airtouch5_client.send_packet.assert_called_once()
    mock_airtouch5_client.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID, ATTR_POSITION: 50},
        blocking=True,
    )
    mock_airtouch5_client.send_packet.assert_called_once()
    mock_airtouch5_client.reset_mock()


async def test_cover_callbacks(
    hass: HomeAssistant,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the callbacks of the Airtouch5 covers."""

    await setup_integration(hass, mock_config_entry)

    # We find the callback method on the mock client
    zone_status_callback: Callable[[dict[int, ZoneStatusZone]], None] = (
        mock_airtouch5_client.zone_status_callbacks[2]
    )

    # Define a method to simply call it
    async def _call_zone_status_callback(open_percentage: int) -> None:
        zsz = ZoneStatusZone(
            zone_power_state=ZonePowerState.ON,
            zone_number=1,
            control_method=ControlMethod.PERCENTAGE_CONTROL,
            open_percentage=open_percentage,
            set_point=None,
            has_sensor=False,
            temperature=None,
            spill_active=False,
            is_low_battery=False,
        )
        zone_status_callback({1: zsz})
        await hass.async_block_till_done()

    # And call it to effectively launch the callback as the server would do

    # Partly open
    await _call_zone_status_callback(0.7)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 70

    # Fully open
    await _call_zone_status_callback(1)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

    # Fully closed
    await _call_zone_status_callback(0.0)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0

    # Partly reopened
    await _call_zone_status_callback(0.3)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 30
