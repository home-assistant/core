"""Test Autoskope device tracker."""

from unittest.mock import AsyncMock

from autoskope_client.models import CannotConnect, InvalidAuth, Vehicle, VehiclePosition
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.autoskope.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities with snapshot."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("speed", "park_mode", "has_position", "expected_icon"),
    [
        (50, False, True, "mdi:car-arrow-right"),
        (0, True, True, "mdi:car-brake-parking"),
        (2, False, True, "mdi:car"),
        (0, False, False, "mdi:car-clock"),
    ],
    ids=["moving", "parked", "idle", "no_position"],
)
async def test_vehicle_icons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    speed: int,
    park_mode: bool,
    has_position: bool,
    expected_icon: str,
) -> None:
    """Test device tracker icon for different vehicle states."""
    position = (
        VehiclePosition(
            latitude=50.1109221,
            longitude=8.6821267,
            speed=speed,
            timestamp="2025-05-28T10:00:00Z",
            park_mode=park_mode,
        )
        if has_position
        else None
    )

    mock_autoskope_client.get_vehicles.return_value = [
        Vehicle(
            id="12345",
            name="Test Vehicle",
            position=position,
            external_voltage=12.5,
            battery_voltage=3.7,
            gps_quality=1.2,
            imei="123456789012345",
            model="Autoskope",
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.test_vehicle")
    assert state is not None
    assert state.attributes["icon"] == expected_icon


async def test_entity_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity becomes unavailable when coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.test_vehicle")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Simulate connection error on next update
    mock_autoskope_client.get_vehicles.side_effect = CannotConnect("Connection lost")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_vehicle")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entity_recovers_after_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    mock_vehicles: list[Vehicle],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity recovers after a transient coordinator error."""
    await setup_integration(hass, mock_config_entry)

    # Simulate error
    mock_autoskope_client.get_vehicles.side_effect = CannotConnect("Connection lost")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.test_vehicle").state == STATE_UNAVAILABLE

    # Recover
    mock_autoskope_client.get_vehicles.side_effect = None
    mock_autoskope_client.get_vehicles.return_value = mock_vehicles
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_vehicle")
    assert state.state != STATE_UNAVAILABLE


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    mock_vehicles: list[Vehicle],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity stays available after successful re-authentication."""
    await setup_integration(hass, mock_config_entry)

    # First get_vehicles raises InvalidAuth, retry after authenticate succeeds
    mock_autoskope_client.get_vehicles.side_effect = [
        InvalidAuth("Token expired"),
        mock_vehicles,
    ]

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_vehicle")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_reauth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    mock_vehicles: list[Vehicle],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity becomes unavailable on permanent auth failure."""
    await setup_integration(hass, mock_config_entry)

    # get_vehicles raises InvalidAuth, and re-authentication also fails
    mock_autoskope_client.get_vehicles.side_effect = InvalidAuth("Token expired")
    mock_autoskope_client.authenticate.side_effect = InvalidAuth("Invalid credentials")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_vehicle")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Clean up side effects to prevent teardown errors
    mock_autoskope_client.get_vehicles.side_effect = None
    mock_autoskope_client.authenticate.side_effect = None
    mock_autoskope_client.get_vehicles.return_value = mock_vehicles


async def test_vehicle_name_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device name updates in device registry when vehicle is renamed."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})
    assert device_entry is not None
    assert device_entry.name == "Test Vehicle"

    # Simulate vehicle rename on Autoskope side
    mock_autoskope_client.get_vehicles.return_value = [
        Vehicle(
            id="12345",
            name="Renamed Vehicle",
            position=VehiclePosition(
                latitude=50.1109221,
                longitude=8.6821267,
                speed=0,
                timestamp="2025-05-28T10:00:00Z",
                park_mode=True,
            ),
            external_voltage=12.5,
            battery_voltage=3.7,
            gps_quality=1.2,
            imei="123456789012345",
            model="Autoskope",
        )
    ]

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Device registry should reflect the new name
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})
    assert device_entry is not None
    assert device_entry.name == "Renamed Vehicle"
