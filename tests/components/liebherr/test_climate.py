"""Test the liebherr climate platform."""

from collections.abc import Awaitable, Callable, Sequence
from unittest.mock import MagicMock

from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    LiebherrBadRequestError,
    LiebherrConnectionError,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.liebherr.climate import LiebherrClimateEntity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def create_device_state(
    controls: Sequence[TemperatureControl] | None = None,
) -> DeviceState:
    """Create a device state with optional temperature controls."""
    return DeviceState(
        device=Device(
            device_id="test_device_id",
            nickname="Test Device",
            device_type=DeviceType.FRIDGE,
        ),
        controls=list(controls) if controls else [],
    )


def create_temp_control(
    zone_id: int = 0,
    value: int | None = 4,
    target: int | None = 5,
    min_temp: int | None = -2,
    max_temp: int | None = 9,
    unit: TemperatureUnit | None = TemperatureUnit.CELSIUS,
    zone_position: ZonePosition | None = None,
    name: str = "Temperature",
) -> TemperatureControl:
    """Create a temperature control with default values."""
    return TemperatureControl(
        name=name,
        type="TemperatureControl",
        zone_id=zone_id,
        zone_position=zone_position,
        value=value,
        target=target,
        min=min_temp,
        max=max_temp,
        unit=unit,
    )


@pytest.fixture
def mock_device_state() -> DeviceState:
    """Return a mock device state with a single zone."""
    return create_device_state([create_temp_control()])


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> Callable[[DeviceState], Awaitable[None]]:
    """Set up the integration and return a function to update device state."""

    async def _setup(device_state: DeviceState) -> None:
        mock_liebherr_client.get_device_state.return_value = device_state
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return _setup


async def test_single_zone_climate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable,
    mock_device_state: DeviceState,
) -> None:
    """Test single zone climate entity setup."""
    await setup_integration(mock_device_state)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_multi_zone_climate_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable,
) -> None:
    """Test multi-zone climate entities with translation keys."""
    device_state = create_device_state(
        [
            create_temp_control(
                zone_id=0,
                zone_position=ZonePosition.TOP,
                name="Top Zone",
            ),
            create_temp_control(
                zone_id=1,
                zone_position=ZonePosition.BOTTOM,
                name="Bottom Zone",
                value=2,
                target=3,
                min_temp=-18,
                max_temp=-10,
            ),
        ]
    )
    await setup_integration(device_state)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    setup_integration: Callable,
    mock_device_state: DeviceState,
) -> None:
    """Test setting temperature."""
    await setup_integration(mock_device_state)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_device", ATTR_TEMPERATURE: 3},
        blocking=True,
    )

    mock_liebherr_client.set_temperature.assert_called_once_with(
        device_id="test_device_id",
        zone_id=0,
        target=3,
        unit=TemperatureUnit.CELSIUS,
    )


@pytest.mark.parametrize(
    ("side_effect", "exception_type"),
    [
        (LiebherrBadRequestError("Invalid"), HomeAssistantError),
        (LiebherrConnectionError("Failed"), HomeAssistantError),
    ],
)
async def test_set_temperature_errors(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    setup_integration: Callable,
    mock_device_state: DeviceState,
    side_effect: Exception,
    exception_type: type[Exception],
) -> None:
    """Test setting temperature with various errors."""
    await setup_integration(mock_device_state)
    mock_liebherr_client.set_temperature.side_effect = side_effect

    with pytest.raises(exception_type):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.test_device", ATTR_TEMPERATURE: 3},
            blocking=True,
        )


async def test_default_min_max_temp(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable,
) -> None:
    """Test default min/max temperatures when not provided."""
    device_state = create_device_state(
        [create_temp_control(min_temp=None, max_temp=None)]
    )
    await setup_integration(device_state)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fahrenheit_temperature_unit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable,
) -> None:
    """Test climate entity with Fahrenheit temperature unit."""
    device_state = create_device_state(
        [
            create_temp_control(
                value=39,
                target=41,
                min_temp=28,
                max_temp=48,
                unit=TemperatureUnit.FAHRENHEIT,
            )
        ]
    )
    await setup_integration(device_state)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_entity_unavailable_when_no_temperature_control(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable,
    mock_device_state: DeviceState,
) -> None:
    """Test entity becomes unavailable when temperature control is missing."""
    await setup_integration(mock_device_state)

    state = hass.states.get("climate.test_device")
    assert state
    assert state.state != "unavailable"

    # Remove all controls
    mock_liebherr_client.get_device_state.return_value = create_device_state([])
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_device")
    assert state
    assert state.state == "unavailable"


async def test_temperature_values_with_none(
    hass: HomeAssistant,
    setup_integration: Callable,
) -> None:
    """Test temperature properties return None when values are None."""
    device_state = create_device_state(
        [create_temp_control(value=None, target=None, min_temp=None, max_temp=None)]
    )
    await setup_integration(device_state)

    state = hass.states.get("climate.test_device")
    assert state
    assert state.attributes.get("current_temperature") is None
    assert state.attributes.get(ATTR_TEMPERATURE) is None


async def test_coordinator_refresh_after_set_temperature(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    setup_integration: Callable,
    mock_device_state: DeviceState,
) -> None:
    """Test coordinator refresh is called after setting temperature successfully."""
    await setup_integration(mock_device_state)
    mock_liebherr_client.get_device_state.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_device", ATTR_TEMPERATURE: 3},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_liebherr_client.get_device_state.called


async def test_set_temperature_with_none_unit(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    setup_integration: Callable,
) -> None:
    """Test setting temperature when control unit is None (defaults to CELSIUS)."""
    device_state = create_device_state([create_temp_control(unit=None)])
    await setup_integration(device_state)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_device", ATTR_TEMPERATURE: 3},
        blocking=True,
    )

    mock_liebherr_client.set_temperature.assert_called_once_with(
        device_id="test_device_id",
        zone_id=0,
        target=3,
        unit=TemperatureUnit.CELSIUS,
    )


async def test_entity_temperature_control_property_edge_cases(
    hass: HomeAssistant,
    setup_integration: Callable,
) -> None:
    """Test temperature_control property returns None when device not in coordinator data."""
    # Create device with one control
    device_state = create_device_state([create_temp_control(zone_id=0)])
    await setup_integration(device_state)

    # Get the entity to test it directly
    entity_id = "climate.test_device"
    state = hass.states.get(entity_id)
    assert state is not None

    # Get climate entity from platform
    climate_entity: LiebherrClimateEntity | None = None
    for entity in hass.data["entity_components"]["climate"].entities:
        if entity.entity_id == entity_id:
            climate_entity = entity
            break

    assert climate_entity is not None

    # Verify temperature_control works normally
    assert climate_entity.temperature_control is not None

    # Directly test edge case: remove device from coordinator data
    orig_data = climate_entity.coordinator.data
    climate_entity.coordinator.data = {}

    # Now temperature_control should return None (covers line 72)
    assert climate_entity.temperature_control is None

    # Restore data
    climate_entity.coordinator.data = orig_data


async def test_zone_translation_key_without_position(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: Callable,
) -> None:
    """Test zone translation key when zone_position is None (fallback to None)."""
    # Create a control without zone_position
    device_state = create_device_state(
        [create_temp_control(zone_id=0, zone_position=None)]
    )
    await setup_integration(device_state)

    # For single zone without position, name should be None (uses model name)
    entry = entity_registry.async_get("climate.test_device")
    assert entry
    # When translation_key is None, entity uses device name
    assert entry.translation_key is None

    # Get climate entity to test _get_zone_translation_key directly
    climate_entity: LiebherrClimateEntity | None = None
    for entity in hass.data["entity_components"]["climate"].entities:
        if entity.entity_id == "climate.test_device":
            climate_entity = entity
            break

    assert climate_entity is not None
    # This should return None (covers line 84) because zone_position is None
    assert climate_entity._get_zone_translation_key() is None
