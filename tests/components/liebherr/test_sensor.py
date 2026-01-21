"""Test the Liebherr sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    LiebherrClient,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.components.liebherr.sensor import SENSOR_TYPES
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def setup_integration(
    hass: HomeAssistant,
    device: Device,
    state: DeviceState,
    api_key: str = "test_api_key",
) -> MockConfigEntry:
    """Set up the integration with provided device and state."""
    mock_client = MagicMock(spec=LiebherrClient)
    mock_client.get_devices = AsyncMock(return_value=[device])
    mock_client.get_device_state = AsyncMock(return_value=state)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": api_key},
        unique_id=api_key,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.liebherr.LiebherrClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_single_zone_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor with single zone device."""
    device = Device(
        device_id="single_zone",
        nickname="Single Zone Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes1234",
    )
    state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=5,
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )

    await setup_integration(hass, device, state)

    entity_id = "sensor.single_zone_fridge"
    assert hass.states.get(entity_id) == snapshot

    # Verify entity registry
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.translation_key is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_multi_zone_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor with multi-zone device."""
    device = Device(
        device_id="multi_zone",
        nickname="Multi Zone Fridge",
        device_type=DeviceType.COMBI,
        device_name="CBNes5678",
    )
    state = DeviceState(
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

    await setup_integration(hass, device, state, api_key="test_multi_zone_key")

    # Verify states
    assert hass.states.get("sensor.multi_zone_fridge_top_zone") == snapshot(
        name="top_zone"
    )
    assert hass.states.get("sensor.multi_zone_fridge_bottom_zone") == snapshot(
        name="bottom_zone"
    )

    # Verify translation keys in registry
    top_zone_entry = entity_registry.async_get("sensor.multi_zone_fridge_top_zone")
    assert top_zone_entry is not None
    assert top_zone_entry.translation_key == "top_zone"

    bottom_zone_entry = entity_registry.async_get(
        "sensor.multi_zone_fridge_bottom_zone"
    )
    assert bottom_zone_entry is not None
    assert bottom_zone_entry.translation_key == "bottom_zone"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_fahrenheit(
    hass: HomeAssistant,
) -> None:
    """Test sensor with Fahrenheit unit."""
    # Test the unit_fn directly with Fahrenheit control
    sensor_description = SENSOR_TYPES[0]

    fahrenheit_control = TemperatureControl(
        zone_id=1,
        zone_position=ZonePosition.TOP,
        name="Fridge",
        type="fridge",
        value=41,
        unit=TemperatureUnit.FAHRENHEIT,
    )

    # Test value_fn
    assert sensor_description.value_fn(fahrenheit_control) == 41.0

    # Test unit_fn - this should return Fahrenheit
    assert sensor_description.unit_fn is not None
    assert (
        sensor_description.unit_fn(fahrenheit_control) == UnitOfTemperature.FAHRENHEIT
    )

    # Test Celsius control for comparison
    celsius_control = TemperatureControl(
        zone_id=1,
        zone_position=ZonePosition.TOP,
        name="Fridge",
        type="fridge",
        value=5,
        unit=TemperatureUnit.CELSIUS,
    )

    assert sensor_description.value_fn(celsius_control) == 5.0
    assert sensor_description.unit_fn(celsius_control) == UnitOfTemperature.CELSIUS


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_none_value(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor with None value."""
    device = Device(
        device_id="none_value_device",
        nickname="None Value Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes7777",
    )
    state = DeviceState(
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

    await setup_integration(hass, device, state, api_key="test_none_value_key")

    assert hass.states.get("sensor.none_value_fridge") == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unavailable_when_control_missing(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor becomes unavailable when temperature control is missing."""
    device = Device(
        device_id="missing_control_device",
        nickname="Missing Control Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="CBNes6666",
    )
    state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=5,
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )

    config_entry = await setup_integration(
        hass, device, state, api_key="test_missing_control_key"
    )

    # Initial state
    assert hass.states.get("sensor.missing_control_fridge") == snapshot(
        name="available"
    )

    # Remove control and refresh
    state_no_controls = DeviceState(device=device, controls=[])
    coordinators = config_entry.runtime_data
    for coordinator in coordinators.values():
        coordinator.data = state_no_controls
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Should now be unavailable
    assert hass.states.get("sensor.missing_control_fridge") == snapshot(
        name="unavailable"
    )
