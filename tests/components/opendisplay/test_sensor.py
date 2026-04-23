"""Test the OpenDisplay sensor platform."""

from copy import deepcopy
from datetime import timedelta
import time
from unittest.mock import MagicMock

from habluetooth import CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
from opendisplay import voltage_to_percent
from opendisplay.models.config import PowerOption
from opendisplay.models.enums import CapacityEstimator, PowerMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import DEVICE_CONFIG, TEST_ADDRESS, VALID_SERVICE_INFO, make_service_info

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)

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


async def test_sensor_entities_usb_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities for a USB-powered Flex device."""
    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_entities_battery_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities for a battery-powered Flex device with LI_ION chemistry."""
    device_config = deepcopy(DEVICE_CONFIG)
    power = device_config.power
    device_config.power = PowerOption(
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
    mock_opendisplay_device.config = device_config

    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_battery_sensors_not_created_for_usb_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery sensors are not created for USB-powered devices."""
    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    assert entity_registry.async_get("sensor.opendisplay_1234_battery") is None
    assert entity_registry.async_get("sensor.opendisplay_1234_battery_voltage") is None


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
    assert entity_registry.async_get("sensor.opendisplay_1234_battery_voltage") is None


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

    # Coordinator has no data; device is visible but no OpenDisplay data parsed
    assert hass.states.get("sensor.opendisplay_1234_temperature").state == STATE_UNKNOWN


async def test_sensor_goes_unavailable_when_device_disappears(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors become unavailable when the device stops advertising."""
    start_monotonic = time.monotonic()
    await _setup_entry(hass, mock_config_entry)

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.opendisplay_1234_temperature").state
        != STATE_UNAVAILABLE
    )

    # Must exceed both the connectable stale threshold (195s) and the
    # unavailability polling interval (300s) to trigger the callback.
    advance = (
        CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        + UNAVAILABLE_TRACK_SECONDS
        + 1
    )
    monotonic_now = start_monotonic + advance
    with (
        patch_bluetooth_time(monotonic_now),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=advance),
        )
        await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.opendisplay_1234_temperature").state
        == STATE_UNAVAILABLE
    )


async def test_battery_sensor_defaults_to_liion_when_capacity_estimator_unset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test battery % sensor uses LI_ION when capacity_estimator is 0 (not configured)."""
    device_config = deepcopy(DEVICE_CONFIG)
    power = device_config.power
    device_config.power = PowerOption(
        power_mode=PowerMode.BATTERY,
        battery_capacity_mah=power.battery_capacity_mah,
        sleep_timeout_ms=power.sleep_timeout_ms,
        tx_power=power.tx_power,
        sleep_flags=power.sleep_flags,
        battery_sense_pin=power.battery_sense_pin,
        battery_sense_enable_pin=power.battery_sense_enable_pin,
        battery_sense_flags=power.battery_sense_flags,
        capacity_estimator=0,  # not configured — defaults to LI_ION in sensor.py
        voltage_scaling_factor=power.voltage_scaling_factor,
        deep_sleep_current_ua=power.deep_sleep_current_ua,
        deep_sleep_time_seconds=power.deep_sleep_time_seconds,
        reserved=power.reserved,
    )
    mock_opendisplay_device.config = device_config

    await _setup_entry(hass, mock_config_entry)
    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    battery_state = hass.states.get("sensor.opendisplay_1234_battery")
    assert battery_state is not None
    # capacity_estimator=0 should fall back to LI_ION, producing the same value as explicit LI_ION
    expected = voltage_to_percent(3700, CapacityEstimator.LI_ION)
    assert battery_state.state == str(expected)
