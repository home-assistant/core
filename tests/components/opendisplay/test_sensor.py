"""Test the OpenDisplay sensor platform."""

from copy import deepcopy
from unittest.mock import MagicMock

from opendisplay.models.config import PowerOption
from opendisplay.models.enums import PowerMode
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_CONFIG, TEST_ADDRESS, VALID_SERVICE_INFO, make_service_info

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the integration and wait for entities to be created."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_before_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors are created but unavailable before data arrives."""
    await _setup_entry(hass, mock_config_entry)

    # All sensors exist but coordinator has no data yet
    assert hass.states.get("sensor.opendisplay_1234_temperature") is not None
    assert (
        hass.states.get("sensor.opendisplay_1234_temperature").state
        == STATE_UNAVAILABLE
    )


async def test_temperature_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that temperature sensor reports the parsed advertisement value."""
    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    # V1_ADVERTISEMENT_DATA encodes temperature_c = 25.0
    state = hass.states.get("sensor.opendisplay_1234_temperature")
    assert state is not None
    assert state.state == "25.0"


async def test_battery_sensors_not_created_for_usb_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery sensors are not created for USB-powered devices."""
    # DEVICE_CONFIG has power_mode=0 (not BATTERY or SOLAR)
    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    # Temperature should be available
    assert hass.states.get("sensor.opendisplay_1234_temperature").state == "25.0"

    # Battery sensors must not exist at all
    assert entity_registry.async_get("sensor.opendisplay_1234_battery") is None
    assert entity_registry.async_get("sensor.opendisplay_1234_voltage") is None


async def test_battery_sensors_with_battery_sense(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test battery sensors when device is battery powered with a known chemistry."""
    # Build a config with BATTERY power mode and LI_ION chemistry
    device_config = deepcopy(DEVICE_CONFIG)
    power = device_config.power
    new_power = PowerOption(
        power_mode=PowerMode.BATTERY,
        battery_capacity_mah=power.battery_capacity_mah,
        sleep_timeout_ms=power.sleep_timeout_ms,
        tx_power=power.tx_power,
        sleep_flags=power.sleep_flags,
        battery_sense_pin=power.battery_sense_pin,
        battery_sense_enable_pin=power.battery_sense_enable_pin,
        battery_sense_flags=power.battery_sense_flags,
        capacity_estimator=1,  # LI_ION
        voltage_scaling_factor=power.voltage_scaling_factor,
        deep_sleep_current_ua=power.deep_sleep_current_ua,
        deep_sleep_time_seconds=power.deep_sleep_time_seconds,
        reserved=power.reserved,
    )
    device_config.power = new_power
    mock_opendisplay_device.config = device_config

    await _setup_entry(hass, mock_config_entry)

    # V1_ADVERTISEMENT_DATA encodes battery_mv=3700, temperature_c=25.0
    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    voltage_state = hass.states.get("sensor.opendisplay_1234_voltage")
    assert voltage_state is not None
    assert voltage_state.state == "3700"

    battery_state = hass.states.get("sensor.opendisplay_1234_battery")
    assert battery_state is not None
    # 3700 mV with LI_ION chemistry should be > 0%
    assert battery_state.state not in (STATE_UNAVAILABLE, "unknown")
    assert int(battery_state.state) > 0


async def test_no_sensors_for_non_flex_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no sensor entities are created for non-Flex devices."""
    mock_opendisplay_device.is_flex = False
    await _setup_entry(hass, mock_config_entry)

    assert entity_registry.async_get("sensor.opendisplay_1234_temperature") is None
    assert entity_registry.async_get("sensor.opendisplay_1234_battery") is None
    assert entity_registry.async_get("sensor.opendisplay_1234_voltage") is None


async def test_coordinator_ignores_unknown_manufacturer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that advertisements from an unknown manufacturer ID are ignored."""
    await _setup_entry(hass, mock_config_entry)

    unknown_service_info = make_service_info(
        address=TEST_ADDRESS,
        manufacturer_data={0x9999: b"\x00" * 14},
    )
    inject_bluetooth_service_info(hass, unknown_service_info)
    await hass.async_block_till_done()

    # Coordinator has no data, all sensors still unavailable
    assert (
        hass.states.get("sensor.opendisplay_1234_temperature").state
        == STATE_UNAVAILABLE
    )
