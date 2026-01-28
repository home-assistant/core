"""Test the Liebherr sensor platform."""

from unittest.mock import MagicMock

from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.liebherr.sensor import SENSOR_TYPES
from homeassistant.const import STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor with default single zone device from fixture."""
    entity_id = "sensor.test_device"
    assert hass.states.get(entity_id) == snapshot

    # Single zone should have no translation key
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.translation_key is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_multi_zone_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor with multi-zone device."""
    device = Device(
        device_id="multi_zone",
        nickname="Multi Zone Fridge",
        device_type=DeviceType.COMBI,
        device_name="CBNes5678",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    mock_liebherr_client.get_device_state.return_value = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=5,
                unit=TemperatureUnit.CELSIUS,
            ),
            TemperatureControl(
                zone_id=2,
                zone_position=ZonePosition.BOTTOM,
                name="Freezer",
                type="freezer",
                value=-18,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify states and translation keys
    for entity_id, translation_key in (
        ("sensor.multi_zone_fridge_top_zone", "top_zone"),
        ("sensor.multi_zone_fridge_bottom_zone", "bottom_zone"),
    ):
        assert hass.states.get(entity_id) == snapshot(name=translation_key)
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.translation_key == translation_key


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_multi_zone_sensor_with_none_zone_position(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test multi-zone sensor with None zone_position falls back to no translation key."""
    device = Device(
        device_id="multi_zone_none_pos",
        nickname="Multi Zone Fridge",
        device_type=DeviceType.COMBI,
        device_name="CBNes9999",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    mock_liebherr_client.get_device_state.return_value = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=None,  # None zone_position
                name="Fridge",
                type="fridge",
                value=5,
                unit=TemperatureUnit.CELSIUS,
            ),
            TemperatureControl(
                zone_id=2,
                zone_position=ZonePosition.BOTTOM,
                name="Freezer",
                type="freezer",
                value=-18,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Zone with None position falls back to entity description name
    zone1_entity = entity_registry.async_get("sensor.multi_zone_fridge_temperature")
    assert zone1_entity is not None
    assert zone1_entity.translation_key is None

    # Zone with valid position should have translation key
    zone2_entity = entity_registry.async_get("sensor.multi_zone_fridge_bottom_zone")
    assert zone2_entity is not None
    assert zone2_entity.translation_key == "bottom_zone"


@pytest.mark.parametrize(
    ("unit", "value", "expected_unit"),
    [
        (TemperatureUnit.CELSIUS, 5, UnitOfTemperature.CELSIUS),
        (TemperatureUnit.FAHRENHEIT, 41, UnitOfTemperature.FAHRENHEIT),
    ],
    ids=["celsius", "fahrenheit"],
)
async def test_sensor_unit_conversion(
    unit: TemperatureUnit,
    value: int,
    expected_unit: str,
) -> None:
    """Test sensor unit conversion functions."""
    sensor_description = SENSOR_TYPES[0]
    control = TemperatureControl(
        zone_id=1,
        zone_position=ZonePosition.TOP,
        name="Fridge",
        type="fridge",
        value=value,
        unit=unit,
    )

    assert sensor_description.value_fn(control) == float(value)
    assert sensor_description.unit_fn(control) == expected_unit


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_none_value(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor with None value."""
    device = Device(
        device_id="none_value_device",
        nickname="None Value Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes7777",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    mock_liebherr_client.get_device_state.return_value = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=None,
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.none_value_fridge") == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_unavailable_when_control_missing(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor becomes unavailable when temperature control is missing."""
    entity_id = "sensor.test_device"

    # Initial state from fixture
    assert hass.states.get(entity_id) == snapshot(name="available")

    # Remove control and push updated data to the coordinator
    device = mock_config_entry.runtime_data["test_device_id"].data.device
    state_no_controls = DeviceState(device=device, controls=[])
    for coordinator in mock_config_entry.runtime_data.values():
        coordinator.async_set_updated_data(state_no_controls)
    await hass.async_block_till_done()

    # Should now be unavailable
    assert hass.states.get(entity_id) == snapshot(name="unavailable")

    # Verify native_value/unit return None when control is missing
    entity = hass.data["entity_components"]["sensor"].get_entity(entity_id)
    assert entity is not None
    assert entity.native_value is None
    assert entity.native_unit_of_measurement is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        LiebherrConnectionError("Connection failed"),
        LiebherrTimeoutError("Timeout"),
        LiebherrAuthenticationError("API key revoked"),
    ],
    ids=["connection_error", "timeout_error", "auth_error"],
)
async def test_sensor_update_errors(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test sensor becomes unavailable when coordinator update fails."""
    entity_id = "sensor.test_device"

    # Initial state should be available
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == "5"

    # Simulate update error
    mock_liebherr_client.get_device_state.side_effect = exception

    # Trigger coordinator refresh
    for coordinator in mock_config_entry.runtime_data.values():
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_UNAVAILABLE
