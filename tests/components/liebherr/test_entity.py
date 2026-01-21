"""Test the Liebherr entity module."""

from unittest.mock import MagicMock

from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.liebherr.coordinator import LiebherrCoordinator
from homeassistant.components.liebherr.entity import (
    ZONE_POSITION_MAP,
    LiebherrEntity,
    LiebherrZoneEntity,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device() -> Device:
    """Return a mock device."""
    return Device(
        device_id="test_device_id",
        nickname="Test Device",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes1234",
    )


@pytest.fixture
def mock_device_no_type() -> Device:
    """Return a mock device without device type."""
    return Device(
        device_id="test_device_id_2",
        nickname=None,
        device_type=None,
        device_name="CBNes5678",
    )


@pytest.fixture
def mock_device_state(mock_device: Device) -> DeviceState:
    """Return a mock device state."""
    return DeviceState(
        device=mock_device,
        controls=[
            TemperatureControl(
                name="Zone 1",
                type="TemperatureControl",
                zone_id=1,
                zone_position=ZonePosition.TOP,
                value=5,
                unit=TemperatureUnit.CELSIUS,
            ),
            TemperatureControl(
                name="Zone 2",
                type="TemperatureControl",
                zone_id=2,
                zone_position=ZonePosition.MIDDLE,
                value=10,
                unit=TemperatureUnit.FAHRENHEIT,
            ),
            TemperatureControl(
                name="Zone 3",
                type="TemperatureControl",
                zone_id=3,
                zone_position=ZonePosition.BOTTOM,
                value=15,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant,
    mock_device_state: DeviceState,
) -> LiebherrCoordinator:
    """Return a mock coordinator."""
    mock_client = MagicMock()
    mock_config_entry = MockConfigEntry(domain="liebherr")

    coordinator = LiebherrCoordinator(
        hass, mock_config_entry, mock_client, "test_device_id"
    )
    # Set coordinator data using the update_coordinator data property
    coordinator.data = mock_device_state
    return coordinator


async def test_liebherr_entity_with_device_type(
    snapshot: SnapshotAssertion,
    mock_coordinator: LiebherrCoordinator,
) -> None:
    """Test LiebherrEntity with device type."""
    entity = LiebherrEntity(mock_coordinator)

    assert entity._attr_has_entity_name is True
    assert entity._attr_device_info == snapshot


async def test_liebherr_entity_without_device_type(
    snapshot: SnapshotAssertion,
    hass: HomeAssistant,
    mock_device_no_type: Device,
) -> None:
    """Test LiebherrEntity without device type."""
    mock_client = MagicMock()
    mock_config_entry = MockConfigEntry(domain="liebherr")

    coordinator = LiebherrCoordinator(
        hass, mock_config_entry, mock_client, "test_device_id_2"
    )

    # Create device state with no device type
    device_state = DeviceState(device=mock_device_no_type, controls=[])
    coordinator.data = device_state

    entity = LiebherrEntity(coordinator)

    assert entity._attr_device_info == snapshot


async def test_liebherr_zone_entity_temperature_control(
    snapshot: SnapshotAssertion,
    mock_coordinator: LiebherrCoordinator,
) -> None:
    """Test LiebherrZoneEntity temperature_control property."""
    zone_entity = LiebherrZoneEntity(mock_coordinator, zone_id=1)

    temp_control = zone_entity.temperature_control
    assert temp_control is not None
    assert temp_control.zone_id == snapshot
    assert temp_control.zone_position == snapshot
    assert temp_control.value == snapshot


async def test_liebherr_zone_entity_temperature_control_not_found(
    mock_coordinator: LiebherrCoordinator,
) -> None:
    """Test LiebherrZoneEntity temperature_control property when zone not found."""
    zone_entity = LiebherrZoneEntity(mock_coordinator, zone_id=999)

    temp_control = zone_entity.temperature_control
    assert temp_control is None


@pytest.mark.parametrize(
    ("zone_id", "expected_key"),
    [
        (1, "top_zone"),
        (2, "middle_zone"),
        (3, "bottom_zone"),
    ],
)
async def test_liebherr_zone_entity_translation_key(
    mock_coordinator: LiebherrCoordinator,
    zone_id: int,
    expected_key: str,
) -> None:
    """Test LiebherrZoneEntity _get_zone_translation_key method."""
    zone_entity = LiebherrZoneEntity(mock_coordinator, zone_id=zone_id)

    translation_key = zone_entity._get_zone_translation_key()
    assert translation_key == expected_key


async def test_liebherr_zone_entity_translation_key_no_control(
    mock_coordinator: LiebherrCoordinator,
) -> None:
    """Test LiebherrZoneEntity _get_zone_translation_key when no control found."""
    zone_entity = LiebherrZoneEntity(mock_coordinator, zone_id=999)

    translation_key = zone_entity._get_zone_translation_key()
    assert translation_key is None


async def test_liebherr_zone_entity_translation_key_invalid_position(
    hass: HomeAssistant,
) -> None:
    """Test LiebherrZoneEntity _get_zone_translation_key with invalid zone position."""
    mock_client = MagicMock()
    mock_config_entry = MockConfigEntry(domain="liebherr")

    coordinator = LiebherrCoordinator(
        hass, mock_config_entry, mock_client, "test_device_id"
    )

    # Create device state with control that has non-ZonePosition value
    mock_device = Device(
        device_id="test_device_id",
        nickname="Test Device",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes1234",
    )

    # Create a temperature control with zone_position as None/invalid
    device_state = DeviceState(
        device=mock_device,
        controls=[
            TemperatureControl(
                name="Zone 1",
                type="TemperatureControl",
                zone_id=1,
                zone_position=None,  # Invalid zone position
                value=5,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )
    coordinator.data = device_state

    zone_entity = LiebherrZoneEntity(coordinator, zone_id=1)
    translation_key = zone_entity._get_zone_translation_key()
    assert translation_key is None


def test_zone_position_map() -> None:
    """Test ZONE_POSITION_MAP constant."""
    assert ZONE_POSITION_MAP[ZonePosition.TOP] == "top_zone"
    assert ZONE_POSITION_MAP[ZonePosition.MIDDLE] == "middle_zone"
    assert ZONE_POSITION_MAP[ZonePosition.BOTTOM] == "bottom_zone"
