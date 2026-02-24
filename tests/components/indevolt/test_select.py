"""Tests for the Indevolt select platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.components.select import SERVICE_SELECT_OPTION
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

KEY_READ_ENERGY_MODE = "7101"
KEY_WRITE_ENERGY_MODE = "47005"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2, 1], indirect=True)
async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select entity registration and states."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize(
    ("option", "expected_value"),
    [
        ("self_consumed_prioritized", 1),
        ("real_time_control", 4),
        ("charge_discharge_schedule", 5),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    option: str,
    expected_value: int,
) -> None:
    """Test selecting all valid energy mode options."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Update mock data to reflect the new value
    mock_indevolt.fetch_data.return_value[KEY_READ_ENERGY_MODE] = expected_value

    # Attempt to change option
    await hass.services.async_call(
        Platform.SELECT,
        SERVICE_SELECT_OPTION,
        {"entity_id": "select.cms_sf2000_energy_mode", "option": option},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_called_with(KEY_WRITE_ENERGY_MODE, expected_value)

    # Verify updated state
    assert (state := hass.states.get("select.cms_sf2000_energy_mode")) is not None
    assert state.state == option


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_select_set_option_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when selecting an option."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Mock set_data to raise an error
    mock_indevolt.set_data.side_effect = HomeAssistantError(
        "Device communication failed"
    )

    # Attempt to change option
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SELECT,
            SERVICE_SELECT_OPTION,
            {
                "entity_id": "select.cms_sf2000_energy_mode",
                "option": "real_time_control",
            },
            blocking=True,
        )

    # Verify set_data was called before failing
    mock_indevolt.set_data.assert_called_once()


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_select_unavailable_outdoor_portable(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entity is unavailable when device is in outdoor/portable mode (value 0)."""

    # Update mock data to fake outdoor/portable mode
    mock_indevolt.fetch_data.return_value[KEY_READ_ENERGY_MODE] = 0

    # Initialize platform to test availability logic
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Verify entity state is unavailable
    assert (state := hass.states.get("select.cms_sf2000_energy_mode")) is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_select_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select entity availability when coordinator fails."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Confirm initial state is available
    assert (state := hass.states.get("select.cms_sf2000_energy_mode")) is not None
    assert state.state != STATE_UNAVAILABLE

    # Simulate a fetch error
    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify entity state is unavailable
    assert (state := hass.states.get("select.cms_sf2000_energy_mode")) is not None
    assert state.state == STATE_UNAVAILABLE
