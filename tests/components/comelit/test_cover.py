"""Tests for Comelit SimpleHome cover platform."""

from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import COVER, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    snapshot_platform,
)

ENTITY_ID = "cover.cover0"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.BRIDGE_PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_serial_bridge_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_serial_bridge_config_entry.entry_id,
    )


async def test_cover_open(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover open service."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING

    # Finish opening, update status
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Cover0",
            status=0,
            human_status="stopped",
            type="cover",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN


async def test_cover_close(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover close and stop service."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Close cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSING

    # Stop cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSED


async def test_cover_stop_if_stopped(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover stop service when already stopped."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Stop cover while not opening/closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_not_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "cover_state",
    [
        CoverState.OPEN,
        CoverState.CLOSED,
    ],
)
async def test_cover_restore_state(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    cover_state: CoverState,
) -> None:
    """Test cover restore state on reload."""

    mock_restore_cache(hass, [State(ENTITY_ID, cover_state)])
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == cover_state


async def test_cover_dynamic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover dynamically added."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert hass.states.get(ENTITY_ID)

    entity_id_2 = "cover.cover1"

    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Cover0",
            status=0,
            human_status="stopped",
            type="cover",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        ),
        1: ComelitSerialBridgeObject(
            index=1,
            name="Cover1",
            status=0,
            human_status="stopped",
            type="cover",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(entity_id_2)
