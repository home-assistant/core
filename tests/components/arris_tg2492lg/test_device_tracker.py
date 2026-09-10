"""Tests for the arris_tg2492lg device tracker."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.arris_tg2492lg.const import SCAN_INTERVAL
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import LATE_DEVICE, MOCK_DEVICES, _create_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_connect_box")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entities are created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_connect_box")
async def test_device_tracker_data_shape(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test offline, MAC-less and duplicate-MAC devices are filtered out."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == DEVICE_TRACKER_DOMAIN
    ]
    # Offline device, MAC-less device and the dual-stack duplicate are dropped.
    assert {entity.unique_id for entity in entities} == {
        "AA:BB:CC:DD:EE:FF",
        "11:22:33:44:55:66",
    }

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "AA:BB:CC:DD:EE:FF"
    assert state.attributes["ip"] == "192.168.178.10"
    assert state.attributes["host_name"] == "my-phone"
    assert state.attributes["source_type"] == "router"
    assert state.attributes["tracking_type"] == "connection"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device goes not_home when it disappears from a successful scan."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME

    # Simulate the phone disconnecting from the router.
    mock_connect_box.async_get_connected_devices.return_value = [
        device for device in MOCK_DEVICES if device.mac != "AA:BB:CC:DD:EE:FF"
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device goes home again with refreshed attributes on reconnect."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_connect_box.async_get_connected_devices.return_value = [
        device for device in MOCK_DEVICES if device.mac != "AA:BB:CC:DD:EE:FF"
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_NOT_HOME

    # The phone reconnects with a new IP address.
    phone = _create_device("AA:BB:CC:DD:EE:FF", "my-phone", "192.168.178.42", True)
    mock_connect_box.async_get_connected_devices.return_value = [phone]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["ip"] == "192.168.178.42"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_late_joiner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device first seen after setup gets a new entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_desktop") is None

    mock_connect_box.async_get_connected_devices.return_value = [
        *MOCK_DEVICES,
        LATE_DEVICE,
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_desktop")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "33:44:55:66:77:88"
