"""Tests for the Indevolt number platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

KEY_READ_DISCHARGE_LIMIT = "6105"
KEY_WRITE_DISCHARGE_LIMIT = "1142"

KEY_READ_MAX_AC_OUTPUT_POWER = "11011"
KEY_WRITE_MAX_AC_OUTPUT_POWER = "1147"

KEY_READ_INVERTER_INPUT_LIMIT = "11009"
KEY_WRITE_INVERTER_INPUT_LIMIT = "1138"

KEY_READ_FEEDIN_POWER_LIMIT = "11010"
KEY_WRITE_FEEDIN_POWER_LIMIT = "1146"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number entity registration and values."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "read_key", "write_key", "test_value"),
    [
        (
            "number.cms_sf2000_discharge_limit",
            KEY_READ_DISCHARGE_LIMIT,
            KEY_WRITE_DISCHARGE_LIMIT,
            50,
        ),
        (
            "number.cms_sf2000_max_ac_output_power",
            KEY_READ_MAX_AC_OUTPUT_POWER,
            KEY_WRITE_MAX_AC_OUTPUT_POWER,
            1500,
        ),
        (
            "number.cms_sf2000_inverter_input_limit",
            KEY_READ_INVERTER_INPUT_LIMIT,
            KEY_WRITE_INVERTER_INPUT_LIMIT,
            800,
        ),
        (
            "number.cms_sf2000_feed_in_power_limit",
            KEY_READ_FEEDIN_POWER_LIMIT,
            KEY_WRITE_FEEDIN_POWER_LIMIT,
            1200,
        ),
    ],
)
async def test_number_set_values(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    read_key: str,
    write_key: str,
    test_value: int,
) -> None:
    """Test setting number values for all configurable parameters."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Update mock data to reflect the new value
    mock_indevolt.fetch_data.return_value[read_key] = test_value

    # Call the service to set the value
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {"entity_id": entity_id, "value": test_value},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_called_with(write_key, test_value)

    # Verify updated state
    assert (state := hass.states.get(entity_id)) is not None
    assert int(float(state.state)) == test_value


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_value_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting number values."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock set_data to raise an error
    mock_indevolt.set_data.side_effect = HomeAssistantError(
        "Device communication failed"
    )

    # Attempt to set value
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {
                "entity_id": "number.cms_sf2000_discharge_limit",
                "value": 50,
            },
            blocking=True,
        )

    # Verify set_data was called before failing
    mock_indevolt.set_data.assert_called_once()


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number entity availability / non-availability."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("number.cms_sf2000_discharge_limit"))
    assert int(float(state.state)) == 5

    # Simulate fetch_data error
    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("number.cms_sf2000_discharge_limit"))
    assert state.state == STATE_UNAVAILABLE
