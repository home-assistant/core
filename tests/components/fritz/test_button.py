"""Tests for Fritz!Tools button platform."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fritz.const import DOMAIN, MeshRoles
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from .const import (
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_MESH_DATA,
    MOCK_NEW_DEVICE_NODE,
    MOCK_USER_DATA,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools buttons."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.BUTTON]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "wrapper_method"),
    [
        ("button.mock_title_firmware_update", "async_trigger_firmware_update"),
        ("button.mock_title_restart", "async_trigger_reboot"),
        ("button.mock_title_reconnect", "async_trigger_reconnect"),
        ("button.mock_title_cleanup", "async_trigger_cleanup"),
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    entity_id: str,
    wrapper_method: str,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test Fritz!Tools buttons."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    button = hass.states.get(entity_id)
    assert button
    assert button.state == STATE_UNKNOWN
    with patch(
        f"homeassistant.components.fritz.coordinator.AvmWrapper.{wrapper_method}"
    ) as mock_press_action:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_press_action.assert_called_once()

        button = hass.states.get(entity_id)
        assert button.state != STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wol_button(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test Fritz!Tools wake on LAN button."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    button = hass.states.get("button.printer_wake_on_lan")
    assert button
    assert button.state == STATE_UNKNOWN
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_wake_on_lan"
    ) as mock_press_action:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.printer_wake_on_lan"},
            blocking=True,
        )
        mock_press_action.assert_called_once_with("AA:BB:CC:00:11:22")

        button = hass.states.get("button.printer_wake_on_lan")
        assert button.state != STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wol_button_new_device(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test WoL button is created for new device at runtime."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    mesh_data = deepcopy(MOCK_MESH_DATA)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("button.printer_wake_on_lan")
    assert not hass.states.get("button.server_wake_on_lan")

    mesh_data["nodes"].append(MOCK_NEW_DEVICE_NODE)
    fh_class_mock.get_mesh_topology.return_value = mesh_data

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("button.printer_wake_on_lan")
    assert hass.states.get("button.server_wake_on_lan")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wol_button_absent_for_mesh_slave(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test WoL button not created if interviewed box is in slave mode."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    slave_mesh_data = deepcopy(MOCK_MESH_DATA)
    slave_mesh_data["nodes"][0]["mesh_role"] = MeshRoles.SLAVE
    fh_class_mock.get_mesh_topology.return_value = slave_mesh_data

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    button = hass.states.get("button.printer_wake_on_lan")
    assert button is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wol_button_absent_for_non_lan_device(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test WoL button not created if interviewed device is not connected via LAN."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    printer_wifi_data = deepcopy(MOCK_MESH_DATA)
    # initialization logic uses the connection type of the `node_interface_1_uid` pair of the printer
    # ni-230 is wifi interface of fritzbox
    printer_node_interface = printer_wifi_data["nodes"][1]["node_interfaces"][0]
    printer_node_interface["type"] = "WLAN"
    printer_node_interface["node_links"][0]["node_interface_1_uid"] = "ni-230"
    fh_class_mock.get_mesh_topology.return_value = printer_wifi_data

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    button = hass.states.get("button.printer_wake_on_lan")
    assert button is None


async def test_cleanup_button(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test cleanup of orphan devices."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # check if tracked device is registered properly
    device = device_registry.async_get_device(
        connections={("mac", "aa:bb:cc:00:11:22")}
    )
    assert device

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.unique_id.startswith("AA:BB:CC:00:11:22")
    ]
    assert entities
    assert len(entities) == 3

    # removed tracked device and trigger cleanup
    host_attributes = deepcopy(MOCK_HOST_ATTRIBUTES_DATA)
    host_attributes.pop(0)
    fh_class_mock.get_hosts_attributes.return_value = host_attributes

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.mock_title_cleanup"},
        blocking=True,
    )

    await hass.async_block_till_done(wait_background_tasks=True)

    # check if orphan tracked device is removed
    device = device_registry.async_get_device(
        connections={("mac", "aa:bb:cc:00:11:22")}
    )
    assert not device

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.unique_id.startswith("AA:BB:CC:00:11:22")
    ]
    assert not entities
