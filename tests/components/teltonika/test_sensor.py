"""Test Teltonika sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor entities match snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_modem_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_modems: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when modem is removed."""

    # Get initial sensor state
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # Update coordinator with empty modem data
    mock_response = MagicMock()
    mock_response.data = []  # No modems
    mock_modems.get_status.return_value = mock_response

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that entity is marked as unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # When modem is removed, entity should be marked as unavailable
    # Verify through entity registry that entity exists but is unavailable
    entity_entry = entity_registry.async_get("sensor.rutx50_test_internal_modem_rssi")
    assert entity_entry is not None
    # State should show unavailable when modem is removed
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_sensor_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable on update failure and recovers."""

    # Get initial sensor state,  here it should be available
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"

    mock_modems.get_status.side_effect = TeltonikaConnectionError("Connection lost")

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"
    # Simulate recovery
    mock_modems.get_status.side_effect = None

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should be available again with correct data
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"


@pytest.mark.parametrize(
    ("side_effect", "expect_reauth"),
    [
        (TeltonikaAuthenticationError("Invalid credentials"), True),
        (TeltonikaConnectionError("Connection lost"), False),
    ],
    ids=["auth_error", "connection_error"],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_update_exception_paths(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
    expect_reauth: bool,
) -> None:
    """Test an auth error triggers reauth while a connection error stays working."""
    mock_modems.get_status.side_effect = side_effect

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    has_reauth = any(
        flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )
    assert has_reauth is expect_reauth


@pytest.mark.usefixtures("init_integration")
async def test_sensor_update_unsuccessful_response(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unsuccessful API response marks entities unavailable without reauth."""
    mock_modems.get_status.side_effect = None
    mock_modems.get_status.return_value = MagicMock(
        success=False,
        data=None,
        errors=[MagicMock(code=999, error="API error")],
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    has_reauth = any(
        flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )
    assert has_reauth is False
