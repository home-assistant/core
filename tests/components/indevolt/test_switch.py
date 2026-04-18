"""Tests for the Indevolt switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

KEY_READ_GRID_CHARGING = "2618"
KEY_WRITE_GRID_CHARGING = "1143"

KEY_READ_LIGHT = "7171"
KEY_WRITE_LIGHT = "7265"

KEY_READ_BYPASS = "680"
KEY_WRITE_BYPASS = "7266"

DEFAULT_STATE_ON = 1
DEFAULT_STATE_OFF = 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entity registration and states."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "read_key", "write_key", "on_value"),
    [
        (
            "switch.cms_sf2000_allow_grid_charging",
            KEY_READ_GRID_CHARGING,
            KEY_WRITE_GRID_CHARGING,
            1001,
        ),
        (
            "switch.cms_sf2000_led_indicator",
            KEY_READ_LIGHT,
            KEY_WRITE_LIGHT,
            DEFAULT_STATE_ON,
        ),
        (
            "switch.cms_sf2000_bypass_socket",
            KEY_READ_BYPASS,
            KEY_WRITE_BYPASS,
            DEFAULT_STATE_ON,
        ),
    ],
)
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    read_key: str,
    write_key: str,
    on_value: int,
) -> None:
    """Test turning switches on."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Update mock data to reflect the new value
    mock_indevolt.fetch_data.return_value[read_key] = on_value

    # Call the service to turn on
    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_called_with(write_key, 1)

    # Verify updated state
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "read_key", "write_key", "off_value"),
    [
        (
            "switch.cms_sf2000_allow_grid_charging",
            KEY_READ_GRID_CHARGING,
            KEY_WRITE_GRID_CHARGING,
            1000,
        ),
        (
            "switch.cms_sf2000_led_indicator",
            KEY_READ_LIGHT,
            KEY_WRITE_LIGHT,
            DEFAULT_STATE_OFF,
        ),
        (
            "switch.cms_sf2000_bypass_socket",
            KEY_READ_BYPASS,
            KEY_WRITE_BYPASS,
            DEFAULT_STATE_OFF,
        ),
    ],
)
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    read_key: str,
    write_key: str,
    off_value: int,
) -> None:
    """Test turning switches off."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Update mock data to reflect the new value
    mock_indevolt.fetch_data.return_value[read_key] = off_value

    # Call the service to turn off
    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_called_with(write_key, 0)

    # Verify updated state
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_set_value_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when toggling a switch."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Mock set_data to raise an error
    mock_indevolt.set_data.side_effect = HomeAssistantError(
        "Device communication failed"
    )

    # Attempt to switch on
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {"entity_id": "switch.cms_sf2000_allow_grid_charging"},
            blocking=True,
        )

    # Verify set_data was called before failing
    mock_indevolt.set_data.assert_called_once()


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch entity availability / non-availability."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Confirm current state is "on"
    assert (state := hass.states.get("switch.cms_sf2000_allow_grid_charging"))
    assert state.state == STATE_ON

    # Simulate fetch_data error
    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Confirm current state is "unavailable"
    assert (state := hass.states.get("switch.cms_sf2000_allow_grid_charging"))
    assert state.state == STATE_UNAVAILABLE
