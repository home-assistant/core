"""Test Flic battery sensors."""

from unittest.mock import MagicMock

from pyflic_ble import DeviceType
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flic_button.sensor import _estimate_battery_percentage
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FLIC2_ADDRESS, setup_integration

BATTERY_ENTITY_ID = "sensor.flic_2_b12345_battery"
VOLTAGE_ENTITY_ID = "sensor.flic_2_b12345_battery_voltage"


@pytest.fixture
def platforms() -> list[Platform]:
    """Set up only sensors."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_flic_client",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("device_type", list(DeviceType))
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Expose voltage for all models and percentage only for Flic 2."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
async def test_voltage_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
) -> None:
    """Only enable the percentage sensor by default."""
    await setup_integration(hass, mock_config_entry)
    entry = entity_registry.async_get(VOLTAGE_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{FLIC2_ADDRESS}-battery_voltage"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(VOLTAGE_ENTITY_ID) is None
    assert hass.states.get(BATTERY_ENTITY_ID) is not None
    mock_flic_client.get_battery_voltage.assert_not_called()
    mock_flic_client.get_battery_level.assert_not_called()


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("connected", [True, False])
async def test_state_update_and_cached_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    connected: bool,
) -> None:
    """Refresh measurements and retain them after disconnection."""
    await setup_integration(hass, mock_config_entry)
    mock_flic_client.state.battery_voltage = 2.9
    mock_flic_client.state.connected = connected
    for registration in mock_flic_client.register_state_callback.call_args_list:
        registration.args[0](mock_flic_client.state)
    await hass.async_block_till_done()
    assert hass.states.get(BATTERY_ENTITY_ID).state == "42"
    assert hass.states.get(VOLTAGE_ENTITY_ID).state == "2.9"
    mock_flic_client.get_battery_voltage.assert_not_called()


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("voltage", [None, float("nan"), float("inf")])
async def test_unknown_battery_voltage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    voltage: float | None,
) -> None:
    """Do not invent a measurement before a valid reading is available."""
    mock_flic_client.state.connected = False
    mock_flic_client.state.battery_voltage = voltage
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(VOLTAGE_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("voltage", "expected"),
    [
        (2.0, 0),
        (2.1, 0),
        (2.27, 3),
        (2.44, 6),
        (2.59, 12),
        (2.74, 18),
        (2.82, 30),
        (2.9, 42),
        (2.95, 71),
        (3.0, 100),
        (3.2, 100),
        (None, None),
    ],
)
def test_manufacturer_battery_curve(
    voltage: float | None, expected: int | None
) -> None:
    """Match the SDK's curve boundaries, interpolation and limits."""
    assert _estimate_battery_percentage(voltage) == expected
