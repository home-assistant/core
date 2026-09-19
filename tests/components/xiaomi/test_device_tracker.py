"""Tests for the xiaomi device tracker."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.xiaomi.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import LATE_DEVICE, MOCK_DEVICE_LIST, _create_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_xiaomi_client")
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_xiaomi_client")
async def test_device_tracker_data_shape(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test offline, MAC-less (missing or empty) and duplicate-MAC devices are filtered out."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == DEVICE_TRACKER_DOMAIN
    ]
    # Offline, MAC-less, empty-MAC and dual-stack duplicate devices are dropped.
    assert {entity.unique_id for entity in entities} == {
        f"{mock_config_entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{mock_config_entry.entry_id}_11:22:33:44:55:66",
    }

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "aa:bb:cc:dd:ee:ff"
    assert state.attributes["ip"] == "192.168.31.10"
    assert state.attributes["host_name"] == "my-phone"
    assert state.attributes["source_type"] == "router"
    assert state.attributes["tracking_type"] == "connection"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_legacy_string_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
) -> None:
    """Test a legacy payload with a plain string IP is handled."""
    legacy_device = _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "192.168.0.50")
    legacy_device["ip"] = "192.168.0.50"
    mock_xiaomi_client.get_device_list.return_value = [legacy_device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.attributes["ip"] == "192.168.0.50"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_without_ip_record(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
) -> None:
    """Test a device without usable IP records still gets an entity."""
    device = _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "")
    device["ip"] = []
    mock_xiaomi_client.get_device_list.return_value = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME
    assert "ip" not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_skips_empty_ip_records(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
) -> None:
    """Test an empty first IP record is skipped in favor of a later one."""
    device = _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "")
    device["ip"] = [{"ip": ""}, {"ip": "192.168.0.99"}]
    mock_xiaomi_client.get_device_list.return_value = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.attributes["ip"] == "192.168.0.99"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_xiaomi_client")
async def test_device_tracker_mac_case_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a MAC casing change between polls keeps the same entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_xiaomi_client.get_device_list.return_value = [
        {**device, "mac": device["mac"].lower()}
        for device in MOCK_DEVICE_LIST
        if device.get("mac")
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == DEVICE_TRACKER_DOMAIN
    ]
    assert {entity.unique_id for entity in entities} == {
        f"{mock_config_entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{mock_config_entry.entry_id}_11:22:33:44:55:66",
    }
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_xiaomi_client")
async def test_device_tracker_two_entries_same_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The same device seen by two configured routers gets one tracker per entry."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JBBBBBBBBBBBBBBBBBBBBBBBBB",
        title="192.168.31.2",
        data={
            CONF_HOST: "192.168.31.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # A second router seeing the same device must not take over its tracker.
    second_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED

    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == DEVICE_TRACKER_DOMAIN
    ]
    assert {entity.unique_id for entity in entities} == {
        f"{mock_config_entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{mock_config_entry.entry_id}_11:22:33:44:55:66",
        f"{second_entry.entry_id}_aa:bb:cc:dd:ee:ff",
        f"{second_entry.entry_id}_11:22:33:44:55:66",
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
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
    mock_xiaomi_client.get_device_list.return_value = [
        device
        for device in MOCK_DEVICE_LIST
        if device.get("mac") != "AA:BB:CC:DD:EE:FF"
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
    mock_xiaomi_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device goes home again with refreshed attributes on reconnect."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_xiaomi_client.get_device_list.return_value = [
        device
        for device in MOCK_DEVICE_LIST
        if device.get("mac") != "AA:BB:CC:DD:EE:FF"
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_NOT_HOME

    # The phone reconnects with a new IP address.
    phone = _create_device("AA:BB:CC:DD:EE:FF", "my-phone", 1, "192.168.31.42")
    mock_xiaomi_client.get_device_list.return_value = [phone]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["ip"] == "192.168.31.42"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_late_joiner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device first seen after setup gets a new entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_desktop") is None

    mock_xiaomi_client.get_device_list.return_value = [*MOCK_DEVICE_LIST, LATE_DEVICE]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_desktop")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "33:44:55:66:77:88"
