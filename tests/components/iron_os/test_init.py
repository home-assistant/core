"""Test init of IronOS integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pynecil import CommunicationError, DeviceInfoResponse
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH

from .conftest import DEFAULT_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_pynecil", "ble_device")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_settings_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test skipping of settings on exception."""
    mock_pynecil.get_settings.side_effect = CommunicationError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("number.pinecil_boost_temperature"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_pynecil", "ble_device"
)
async def test_v223_entities_not_loaded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test the new entities in IronOS v2.23 are not loaded on smaller versions."""

    mock_pynecil.get_device_info.return_value = DeviceInfoResponse(
        build="v2.22",
        device_id="c0ffeeC0",
        address="c0:ff:ee:c0:ff:ee",
        device_sn="0000c0ffeec0ffee",
        name=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("number.pinecil_hall_sensor_sleep_timeout") is None
    assert hass.states.get("select.pinecil_soldering_tip_type") is None
    assert (
        state := hass.states.get("select.pinecil_power_delivery_3_1_epr")
    ) is not None

    assert len(state.attributes["options"]) == 2


@pytest.mark.usefixtures("ble_device")
async def test_device_info_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device info gets updated."""

    mock_pynecil.get_device_info.return_value = DeviceInfoResponse()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        connections={(CONNECTION_BLUETOOTH, config_entry.unique_id)}
    )
    assert device
    assert device.sw_version is None
    assert device.serial_number is None

    mock_pynecil.get_device_info.return_value = DeviceInfoResponse(
        build="v2.22",
        device_id="c0ffeeC0",
        address="c0:ff:ee:c0:ff:ee",
        device_sn="0000c0ffeec0ffee",
        name=DEFAULT_NAME,
    )

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(CONNECTION_BLUETOOTH, config_entry.unique_id)}
    )
    assert device
    assert device.sw_version == "v2.22"
    assert device.serial_number == "0000c0ffeec0ffee (ID:c0ffeeC0)"
