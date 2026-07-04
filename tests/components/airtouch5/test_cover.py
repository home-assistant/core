"""Tests for the Airtouch5 cover platform."""

from unittest.mock import AsyncMock, patch

from airtouch5py.packets.zone_status import (
    ControlMethod,
    ZonePowerState,
    ZoneStatusZone,
)
from syrupy.assertion import SnapshotAssertion

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
COVER_ZONE_2_ENTITY_ID = "cover.zone_2_damper"


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

    # Capture initial state of zone 2 cover to verify it's unaffected
    zone_2_initial = hass.states.get(COVER_ZONE_2_ENTITY_ID)
    assert zone_2_initial
    zone_2_initial_state = zone_2_initial.state
    zone_2_initial_position = zone_2_initial.attributes.get(ATTR_CURRENT_POSITION)

    # Define a method to call all zone_status_callbacks, as the real client would
    async def _call_zone_status_callback(open_percentage: float) -> None:
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
        data = {1: zsz}
        for callback in mock_airtouch5_client.zone_status_callbacks:
            callback(data)
        await hass.async_block_till_done()

    # And call it to effectively launch the callback as the server would do

    # Partly open
    await _call_zone_status_callback(0.7)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 70
    zone_2 = hass.states.get(COVER_ZONE_2_ENTITY_ID)
    assert zone_2 and zone_2.state == zone_2_initial_state
    assert zone_2.attributes.get(ATTR_CURRENT_POSITION) == zone_2_initial_position

    # Fully open
    await _call_zone_status_callback(1)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100
    zone_2 = hass.states.get(COVER_ZONE_2_ENTITY_ID)
    assert zone_2 and zone_2.state == zone_2_initial_state
    assert zone_2.attributes.get(ATTR_CURRENT_POSITION) == zone_2_initial_position

    # Fully closed
    await _call_zone_status_callback(0.0)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0
    zone_2 = hass.states.get(COVER_ZONE_2_ENTITY_ID)
    assert zone_2 and zone_2.state == zone_2_initial_state
    assert zone_2.attributes.get(ATTR_CURRENT_POSITION) == zone_2_initial_position

    # Partly reopened
    await _call_zone_status_callback(0.3)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 30
    zone_2 = hass.states.get(COVER_ZONE_2_ENTITY_ID)
    assert zone_2 and zone_2.state == zone_2_initial_state
    assert zone_2.attributes.get(ATTR_CURRENT_POSITION) == zone_2_initial_position
