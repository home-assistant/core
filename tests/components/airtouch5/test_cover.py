"""Tests for the Airtouch5 cover platform."""

<<<<<<< HEAD
from asyncio import sleep
=======
>>>>>>> ed88036ce95 (removing fragile list index)
from collections.abc import Callable
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
    mock_airtouch_discovery: AsyncMock,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.airtouch5.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_actions(
    hass: HomeAssistant,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_airtouch_discovery: AsyncMock,
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
    mock_airtouch_discovery: AsyncMock,
) -> None:
    """Test the callbacks of the Airtouch5 covers."""

    # Patch migration to avoid race conditions with minor_version
    with patch(
        "homeassistant.components.airtouch5.async_migrate_entry",
        new=AsyncMock(return_value=True),
    ):
        # Setup the integration normally
        await setup_integration(hass, mock_config_entry)

        # Get the registered zone status callback
        zone_status_callback: Callable[[dict[int, ZoneStatusZone]], None] = next(
            cb
            for cb in mock_airtouch5_client.zone_status_callbacks
            if getattr(cb.__self__, "entity_id", "").startswith(COVER_ENTITY_ID)
        )

        # Helper to trigger the callback and let HA process updates
        async def _trigger_callback(open_percentage: float) -> None:
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
            # Ensure Home Assistant finishes processing
            await hass.async_block_till_done()

<<<<<<< HEAD
        # And call it to effectively launch the callback as the server would do

        # Partly open
        await _call_zone_status_callback(0.7)
        await sleep(0.01)  # let the loop process state updates
=======
        # Test various positions

        # Partly open (70%)
        await _trigger_callback(0.7)
>>>>>>> ed88036ce95 (removing fragile list index)
        state = hass.states.get(COVER_ENTITY_ID)
        assert state
        assert state.state == CoverState.OPEN
        assert state.attributes.get(ATTR_CURRENT_POSITION) == 70

<<<<<<< HEAD
    # Fully open
    await _call_zone_status_callback(1)
    state = hass.states.get(COVER_ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

        # Fully closed
        await _call_zone_status_callback(0.0)
        await sleep(0.01)  # let the loop process state updates
=======
        # Fully open (100%)
        await _trigger_callback(1)
        state = hass.states.get(COVER_ENTITY_ID)
        assert state
        assert state.state == CoverState.OPEN
        assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

        # Fully closed (0%)
        await _trigger_callback(0.0)
>>>>>>> ed88036ce95 (removing fragile list index)
        state = hass.states.get(COVER_ENTITY_ID)
        assert state
        assert state.state == CoverState.CLOSED
        assert state.attributes.get(ATTR_CURRENT_POSITION) == 0

<<<<<<< HEAD
        # Partly reopened
        await _call_zone_status_callback(0.3)
        await sleep(0.01)  # let the loop process state updates
=======
        # Partly reopened (30%)
        await _trigger_callback(0.3)
>>>>>>> ed88036ce95 (removing fragile list index)
        state = hass.states.get(COVER_ENTITY_ID)
        assert state
        assert state.state == CoverState.OPEN
        assert state.attributes.get(ATTR_CURRENT_POSITION) == 30
