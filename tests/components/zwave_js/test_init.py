"""Test the Z-Wave JS init module."""
from copy import deepcopy
from unittest.mock import call, patch

import pytest
from zwave_js_server.event import Event
from zwave_js_server.exceptions import BaseZwaveJSServerError, InvalidServerVersion
from zwave_js_server.model.node import Node

from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.config_entries import DISABLED_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import AIR_TEMPERATURE_SENSOR, EATON_RF9640_ENTITY

from tests.common import MockConfigEntry


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture():
    """Mock the connect timeout."""
    with patch("homeassistant.components.zwave_js.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


async def test_entry_setup_unload(hass, client, integration):
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_home_assistant_stop(hass, client, integration):
    """Test we clean up on home assistant stop."""
    await hass.async_stop()

    assert client.disconnect.call_count == 1


async def test_initialized_timeout(hass, client, connect_timeout):
    """Test we handle a timeout during client initialization."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_enabled_statistics(hass, client):
    """Test that we enabled statistics if the entry is opted in."""
    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    entry.add_to_hass(hass)

    with patch(
        "zwave_js_server.model.driver.Driver.async_enable_statistics"
    ) as mock_cmd:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_cmd.called


async def test_disabled_statistics(hass, client):
    """Test that we diisabled statistics if the entry is opted out."""
    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": False},
    )
    entry.add_to_hass(hass)

    with patch(
        "zwave_js_server.model.driver.Driver.async_disable_statistics"
    ) as mock_cmd:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_cmd.called


async def test_noop_statistics(hass, client):
    """Test that we don't make any statistics calls if user hasn't provided preference."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    with patch(
        "zwave_js_server.model.driver.Driver.async_enable_statistics"
    ) as mock_cmd1, patch(
        "zwave_js_server.model.driver.Driver.async_disable_statistics"
    ) as mock_cmd2:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not mock_cmd1.called
        assert not mock_cmd2.called


@pytest.mark.parametrize("error", [BaseZwaveJSServerError("Boom"), Exception("Boom")])
async def test_listen_failure(hass, client, error):
    """Test we handle errors during client listen."""

    async def listen(driver_ready):
        """Mock the client listen method."""
        # Set the connect side effect to stop an endless loop on reload.
        client.connect.side_effect = BaseZwaveJSServerError("Boom")
        raise error

    client.listen.side_effect = listen
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_new_entity_on_value_added(hass, multisensor_6, client, integration):
    """Test we create a new entity if a value is added after the fact."""
    node: Node = multisensor_6

    # Add a value on a random endpoint so we can be sure we should get a new entity
    event = Event(
        type="value added",
        data={
            "source": "node",
            "event": "value added",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 10,
                "property": "Ultraviolet",
                "propertyName": "Ultraviolet",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Ultraviolet",
                    "ccSpecific": {"sensorType": 27, "scale": 0},
                },
                "value": 0,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.multisensor_6_ultraviolet_10") is not None


async def test_on_node_added_ready(hass, multisensor_6_state, client, integration):
    """Test we handle a ready node added event."""
    dev_reg = dr.async_get(hass)
    node = Node(client, multisensor_6_state)
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not dev_reg.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert dev_reg.async_get_device(identifiers={(DOMAIN, air_temperature_device_id)})


async def test_on_node_added_not_ready(hass, multisensor_6_state, client, integration):
    """Test we handle a non ready node added event."""
    dev_reg = dr.async_get(hass)
    node_data = deepcopy(multisensor_6_state)  # Copy to allow modification in tests.
    node = Node(client, node_data)
    node.data["ready"] = False
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not dev_reg.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity not yet added but device added in registry
    assert dev_reg.async_get_device(identifiers={(DOMAIN, air_temperature_device_id)})

    node.data["ready"] = True
    node.emit("ready", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity added
    assert state.state != STATE_UNAVAILABLE


async def test_existing_node_ready(hass, client, multisensor_6, integration):
    """Test we handle a ready node that exists during integration setup."""
    dev_reg = dr.async_get(hass)
    node = multisensor_6
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert dev_reg.async_get_device(identifiers={(DOMAIN, air_temperature_device_id)})


async def test_null_name(hass, client, null_name_check, integration):
    """Test that node without a name gets a generic node name."""
    node = null_name_check
    assert hass.states.get(f"switch.node_{node.node_id}")


async def test_existing_node_not_ready(hass, client, multisensor_6):
    """Test we handle a non ready node that exists during integration setup."""
    dev_reg = dr.async_get(hass)
    node = multisensor_6
    node.data = deepcopy(node.data)  # Copy to allow modification in tests.
    node.data["ready"] = False
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity not yet added
    assert dev_reg.async_get_device(  # device should be added
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    node.data["ready"] = True
    node.emit("ready", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert dev_reg.async_get_device(identifiers={(DOMAIN, air_temperature_device_id)})


async def test_start_addon(
    hass, addon_installed, install_addon, addon_options, set_addon_options, start_addon
):
    """Test start the Z-Wave JS add-on during entry setup."""
    device = "/test"
    network_key = "abc123"
    addon_options = {
        "device": device,
        "network_key": network_key,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"use_addon": True, "usb_path": device, "network_key": network_key},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 0
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        hass, "core_zwave_js", {"options": addon_options}
    )
    assert start_addon.call_count == 1
    assert start_addon.call_args == call(hass, "core_zwave_js")


async def test_install_addon(
    hass, addon_installed, install_addon, addon_options, set_addon_options, start_addon
):
    """Test install and start the Z-Wave JS add-on during entry setup."""
    addon_installed.return_value["version"] = None
    device = "/test"
    network_key = "abc123"
    addon_options = {
        "device": device,
        "network_key": network_key,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"use_addon": True, "usb_path": device, "network_key": network_key},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert install_addon.call_args == call(hass, "core_zwave_js")
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        hass, "core_zwave_js", {"options": addon_options}
    )
    assert start_addon.call_count == 1
    assert start_addon.call_args == call(hass, "core_zwave_js")


@pytest.mark.parametrize("addon_info_side_effect", [HassioAPIError("Boom")])
async def test_addon_info_failure(
    hass,
    addon_installed,
    install_addon,
    addon_options,
    set_addon_options,
    start_addon,
):
    """Test failure to get add-on info for Z-Wave JS add-on during entry setup."""
    device = "/test"
    network_key = "abc123"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"use_addon": True, "usb_path": device, "network_key": network_key},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.parametrize(
    "old_device, new_device, old_network_key, new_network_key",
    [("/old_test", "/new_test", "old123", "new123")],
)
async def test_addon_options_changed(
    hass,
    client,
    addon_installed,
    addon_running,
    install_addon,
    addon_options,
    start_addon,
    old_device,
    new_device,
    old_network_key,
    new_network_key,
):
    """Test update config entry data on entry setup if add-on options changed."""
    addon_options["device"] = new_device
    addon_options["network_key"] = new_network_key
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": old_device,
            "network_key": old_network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.data["usb_path"] == new_device
    assert entry.data["network_key"] == new_network_key
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.parametrize(
    "addon_version, update_available, update_calls, backup_calls, "
    "update_addon_side_effect, create_backup_side_effect",
    [
        ("1.0", True, 1, 1, None, None),
        ("1.0", False, 0, 0, None, None),
        ("1.0", True, 1, 1, HassioAPIError("Boom"), None),
        ("1.0", True, 0, 1, None, HassioAPIError("Boom")),
    ],
)
async def test_update_addon(
    hass,
    client,
    addon_info,
    addon_installed,
    addon_running,
    create_backup,
    update_addon,
    addon_options,
    addon_version,
    update_available,
    update_calls,
    backup_calls,
    update_addon_side_effect,
    create_backup_side_effect,
):
    """Test update the Z-Wave JS add-on during entry setup."""
    device = "/test"
    network_key = "abc123"
    addon_options["device"] = device
    addon_options["network_key"] = network_key
    addon_info.return_value["version"] = addon_version
    addon_info.return_value["update_available"] = update_available
    create_backup.side_effect = create_backup_side_effect
    update_addon.side_effect = update_addon_side_effect
    client.connect.side_effect = InvalidServerVersion("Invalid version")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": device,
            "network_key": network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert create_backup.call_count == backup_calls
    assert update_addon.call_count == update_calls


@pytest.mark.parametrize(
    "stop_addon_side_effect, entry_state",
    [
        (None, ConfigEntryState.NOT_LOADED),
        (HassioAPIError("Boom"), ConfigEntryState.LOADED),
    ],
)
async def test_stop_addon(
    hass,
    client,
    addon_installed,
    addon_running,
    addon_options,
    stop_addon,
    stop_addon_side_effect,
    entry_state,
):
    """Test stop the Z-Wave JS add-on on entry unload if entry is disabled."""
    stop_addon.side_effect = stop_addon_side_effect
    device = "/test"
    network_key = "abc123"
    addon_options["device"] = device
    addon_options["network_key"] = network_key
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": device,
            "network_key": network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_set_disabled_by(entry.entry_id, DISABLED_USER)
    await hass.async_block_till_done()

    assert entry.state == entry_state
    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_zwave_js")


async def test_remove_entry(
    hass, addon_installed, stop_addon, create_backup, uninstall_addon, caplog
):
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call(hass, "core_zwave_js")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_zwave_js")
    assert create_backup.call_count == 0
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the Z-Wave JS add-on" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test create backup failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    create_backup.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to create a backup of the Z-Wave JS add-on" in caplog.text
    create_backup.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call(hass, "core_zwave_js")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Z-Wave JS add-on" in caplog.text


async def test_removed_device(hass, client, multiple_devices, integration):
    """Test that the device registry gets updated when a device gets removed."""
    nodes = multiple_devices

    # Verify how many nodes are available
    assert len(client.driver.controller.nodes) == 2

    # Make sure there are the same number of devices
    dev_reg = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(dev_reg, integration.entry_id)
    assert len(device_entries) == 2

    # Check how many entities there are
    ent_reg = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(ent_reg, integration.entry_id)
    assert len(entity_entries) == 26

    # Remove a node and reload the entry
    old_node = nodes.pop(13)
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Assert that the node and all of it's entities were removed from the device and
    # entity registry
    device_entries = dr.async_entries_for_config_entry(dev_reg, integration.entry_id)
    assert len(device_entries) == 1
    entity_entries = er.async_entries_for_config_entry(ent_reg, integration.entry_id)
    assert len(entity_entries) == 16
    assert dev_reg.async_get_device({get_device_id(client, old_node)}) is None


async def test_suggested_area(hass, client, eaton_rf9640_dimmer):
    """Test that suggested area works."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = ent_reg.async_get(EATON_RF9640_ENTITY)
    assert dev_reg.async_get(entity.device_id).area_id is not None
