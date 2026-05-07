"""Tests for Thomson device tracker."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import MOCK_TELNET_OUTPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test device tracker entities are created."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get("device_tracker.my_phone")
    assert state is not None
    assert state.state == STATE_HOME

    state = hass.states.get("device_tracker.my_laptop")
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_device_tracker_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test device tracker entity attributes."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get("device_tracker.my_phone")
    assert state is not None
    assert state.attributes["ip"] == "192.168.1.100"
    assert state.attributes["mac"] == "AA:BB:CC:DD:EE:FF"
    assert state.attributes["host_name"] == "my-phone"
    assert state.attributes["source_type"] == "router"


async def test_device_tracker_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test device tracker entity unique IDs."""
    await _setup_entry(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("device_tracker.my_phone")
    assert entry is not None
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"

    entry = ent_reg.async_get("device_tracker.my_laptop")
    assert entry is not None
    assert entry.unique_id == "11:22:33:44:55:66"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_device_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test device becomes not_home when disconnected."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get("device_tracker.my_phone")
    assert state is not None
    assert state.state == STATE_HOME

    with patch("homeassistant.components.thomson.coordinator.telnetlib.Telnet") as mock_new:
        telnet_instance = MagicMock()
        mock_new.return_value = telnet_instance
        telnet_instance.read_until.side_effect = [
            b"Username : ",
            b"Password : ",
            b"=>",
            b"=>",
        ]
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("device_tracker.my_phone")
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_filtered_disconnected_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test that devices with status not containing 'C' are filtered out."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get("device_tracker.old_device")
    assert state is None


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_new_device_added_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that new devices are added on coordinator update."""
    await _setup_entry(hass, mock_config_entry)

    assert hass.states.get("device_tracker.my_phone") is not None
    assert hass.states.get("device_tracker.my_laptop") is not None

    new_mac = "FF:EE:DD:CC:BB:AA"
    config_entry_other = MockConfigEntry(domain="something_else_2")
    config_entry_other.add_to_hass(hass)
    device_registry.async_get_or_create(
        name=f"Device {new_mac}",
        config_entry_id=config_entry_other.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, new_mac)},
    )

    new_output = (
        MOCK_TELNET_OUTPUT
        + b"ff:ee:dd:cc:bb:aa 192.168.1.200  C     dynamic  nas  eth0  new-device\r\n"
    )

    with patch("homeassistant.components.thomson.coordinator.telnetlib.Telnet") as mock_new:
        telnet_instance = MagicMock()
        mock_new.return_value = telnet_instance
        telnet_instance.read_until.side_effect = [
            b"Username : ",
            b"Password : ",
            b"=>",
            new_output + b"=>",
        ]
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("device_tracker.new_device")
    assert state is not None
    assert state.state == STATE_HOME


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_telnet: MagicMock,
) -> None:
    """Test unloading a config entry."""
    await _setup_entry(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
