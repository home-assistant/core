"""Provide common Z-Wave JS fixtures."""
import asyncio
import copy
import json
from unittest.mock import AsyncMock, patch

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node
from zwave_js_server.version import VersionInfo

from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from tests.common import MockConfigEntry, load_fixture

# Add-on fixtures


@pytest.fixture(name="addon_info_side_effect")
def addon_info_side_effect_fixture():
    """Return the add-on info side effect."""
    return None


@pytest.fixture(name="addon_info")
def mock_addon_info(addon_info_side_effect):
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_get_addon_info",
        side_effect=addon_info_side_effect,
    ) as addon_info:
        addon_info.return_value = {}
        yield addon_info


@pytest.fixture(name="addon_running")
def mock_addon_running(addon_info):
    """Mock add-on already running."""
    addon_info.return_value["state"] = "started"
    return addon_info


@pytest.fixture(name="addon_installed")
def mock_addon_installed(addon_info):
    """Mock add-on already installed but not running."""
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0"
    return addon_info


@pytest.fixture(name="addon_options")
def mock_addon_options(addon_info):
    """Mock add-on options."""
    addon_info.return_value["options"] = {}
    return addon_info.return_value["options"]


@pytest.fixture(name="set_addon_options_side_effect")
def set_addon_options_side_effect_fixture():
    """Return the set add-on options side effect."""
    return None


@pytest.fixture(name="set_addon_options")
def mock_set_addon_options(set_addon_options_side_effect):
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_set_addon_options",
        side_effect=set_addon_options_side_effect,
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon")
def mock_install_addon():
    """Mock install add-on."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_install_addon"
    ) as install_addon:
        yield install_addon


@pytest.fixture(name="update_addon")
def mock_update_addon():
    """Mock update add-on."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_update_addon"
    ) as update_addon:
        yield update_addon


@pytest.fixture(name="start_addon_side_effect")
def start_addon_side_effect_fixture():
    """Return the set add-on options side effect."""
    return None


@pytest.fixture(name="start_addon")
def mock_start_addon(start_addon_side_effect):
    """Mock start add-on."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_start_addon",
        side_effect=start_addon_side_effect,
    ) as start_addon:
        yield start_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture():
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture():
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


@pytest.fixture(name="create_shapshot")
def create_snapshot_fixture():
    """Mock create snapshot."""
    with patch(
        "homeassistant.components.zwave_js.addon.async_create_snapshot"
    ) as create_shapshot:
        yield create_shapshot


@pytest.fixture(name="device_registry")
async def device_registry_fixture(hass):
    """Return the device registry."""
    return async_get_device_registry(hass)


@pytest.fixture(name="controller_state", scope="session")
def controller_state_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("zwave_js/controller_state.json"))


@pytest.fixture(name="version_state", scope="session")
def version_state_fixture():
    """Load the version state fixture data."""
    return {
        "type": "version",
        "driverVersion": "6.0.0-beta.0",
        "serverVersion": "1.0.0",
        "homeId": 1234567890,
    }


@pytest.fixture(name="multisensor_6_state", scope="session")
def multisensor_6_state_fixture():
    """Load the multisensor 6 node state fixture data."""
    return json.loads(load_fixture("zwave_js/multisensor_6_state.json"))


@pytest.fixture(name="ecolink_door_sensor_state", scope="session")
def ecolink_door_sensor_state_fixture():
    """Load the Ecolink Door/Window Sensor node state fixture data."""
    return json.loads(load_fixture("zwave_js/ecolink_door_sensor_state.json"))


@pytest.fixture(name="hank_binary_switch_state", scope="session")
def binary_switch_state_fixture():
    """Load the hank binary switch node state fixture data."""
    return json.loads(load_fixture("zwave_js/hank_binary_switch_state.json"))


@pytest.fixture(name="bulb_6_multi_color_state", scope="session")
def bulb_6_multi_color_state_fixture():
    """Load the bulb 6 multi-color node state fixture data."""
    return json.loads(load_fixture("zwave_js/bulb_6_multi_color_state.json"))


@pytest.fixture(name="eaton_rf9640_dimmer_state", scope="session")
def eaton_rf9640_dimmer_state_fixture():
    """Load the eaton rf9640 dimmer node state fixture data."""
    return json.loads(load_fixture("zwave_js/eaton_rf9640_dimmer_state.json"))


@pytest.fixture(name="lock_schlage_be469_state", scope="session")
def lock_schlage_be469_state_fixture():
    """Load the schlage lock node state fixture data."""
    return json.loads(load_fixture("zwave_js/lock_schlage_be469_state.json"))


@pytest.fixture(name="lock_august_asl03_state", scope="session")
def lock_august_asl03_state_fixture():
    """Load the August Pro lock node state fixture data."""
    return json.loads(load_fixture("zwave_js/lock_august_asl03_state.json"))


@pytest.fixture(name="climate_radio_thermostat_ct100_plus_state", scope="session")
def climate_radio_thermostat_ct100_plus_state_fixture():
    """Load the climate radio thermostat ct100 plus node state fixture data."""
    return json.loads(
        load_fixture("zwave_js/climate_radio_thermostat_ct100_plus_state.json")
    )


@pytest.fixture(
    name="climate_radio_thermostat_ct100_plus_different_endpoints_state",
    scope="session",
)
def climate_radio_thermostat_ct100_plus_different_endpoints_state_fixture():
    """Load the thermostat fixture state with values on different endpoints.

    This device is a radio thermostat ct100.
    """
    return json.loads(
        load_fixture(
            "zwave_js/climate_radio_thermostat_ct100_plus_different_endpoints_state.json"
        )
    )


@pytest.fixture(name="climate_danfoss_lc_13_state", scope="session")
def climate_danfoss_lc_13_state_fixture():
    """Load the climate Danfoss (LC-13) electronic radiator thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_danfoss_lc_13_state.json"))


@pytest.fixture(name="climate_eurotronic_spirit_z_state", scope="session")
def climate_eurotronic_spirit_z_state_fixture():
    """Load the climate Eurotronic Spirit Z thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_eurotronic_spirit_z_state.json"))


@pytest.fixture(name="climate_heatit_z_trm3_state", scope="session")
def climate_heatit_z_trm3_state_fixture():
    """Load the climate HEATIT Z-TRM3 thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_heatit_z_trm3_state.json"))


@pytest.fixture(name="nortek_thermostat_state", scope="session")
def nortek_thermostat_state_fixture():
    """Load the nortek thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/nortek_thermostat_state.json"))


@pytest.fixture(name="srt321_hrt4_zw_state", scope="session")
def srt321_hrt4_zw_state_fixture():
    """Load the climate HRT4-ZW / SRT321 / SRT322 thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/srt321_hrt4_zw_state.json"))


@pytest.fixture(name="chain_actuator_zws12_state", scope="session")
def window_cover_state_fixture():
    """Load the window cover node state fixture data."""
    return json.loads(load_fixture("zwave_js/chain_actuator_zws12_state.json"))


@pytest.fixture(name="in_wall_smart_fan_control_state", scope="session")
def in_wall_smart_fan_control_state_fixture():
    """Load the fan node state fixture data."""
    return json.loads(load_fixture("zwave_js/in_wall_smart_fan_control_state.json"))


@pytest.fixture(name="gdc_zw062_state", scope="session")
def motorized_barrier_cover_state_fixture():
    """Load the motorized barrier cover node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_zw062_state.json"))


@pytest.fixture(name="iblinds_v2_state", scope="session")
def iblinds_v2_state_fixture():
    """Load the iBlinds v2 node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_iblinds_v2_state.json"))


@pytest.fixture(name="aeon_smart_switch_6_state", scope="session")
def aeon_smart_switch_6_state_fixture():
    """Load the AEON Labs (ZW096) Smart Switch 6 node state fixture data."""
    return json.loads(load_fixture("zwave_js/aeon_smart_switch_6_state.json"))


@pytest.fixture(name="ge_12730_state", scope="session")
def ge_12730_state_fixture():
    """Load the GE 12730 node state fixture data."""
    return json.loads(load_fixture("zwave_js/fan_ge_12730_state.json"))


@pytest.fixture(name="aeotec_radiator_thermostat_state", scope="session")
def aeotec_radiator_thermostat_state_fixture():
    """Load the Aeotec Radiator Thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/aeotec_radiator_thermostat_state.json"))


@pytest.fixture(name="inovelli_lzw36_state", scope="session")
def inovelli_lzw36_state_fixture():
    """Load the Inovelli LZW36 node state fixture data."""
    return json.loads(load_fixture("zwave_js/inovelli_lzw36_state.json"))


@pytest.fixture(name="null_name_check_state", scope="session")
def null_name_check_state_fixture():
    """Load the null name check node state fixture data."""
    return json.loads(load_fixture("zwave_js/null_name_check_state.json"))


@pytest.fixture(name="lock_id_lock_as_id150_state", scope="session")
def lock_id_lock_as_id150_state_fixture():
    """Load the id lock id-150 lock node state fixture data."""
    return json.loads(load_fixture("zwave_js/lock_id_lock_as_id150_state.json"))


@pytest.fixture(
    name="climate_radio_thermostat_ct101_multiple_temp_units_state", scope="session"
)
def climate_radio_thermostat_ct101_multiple_temp_units_state_fixture():
    """Load the climate multiple temp units node state fixture data."""
    return json.loads(
        load_fixture(
            "zwave_js/climate_radio_thermostat_ct101_multiple_temp_units_state.json"
        )
    )


@pytest.fixture(
    name="climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state",
    scope="session",
)
def climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state_fixture():
    """Load the climate device with mode and setpoint on different endpoints node state fixture data."""
    return json.loads(
        load_fixture(
            "zwave_js/climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state.json"
        )
    )


@pytest.fixture(name="vision_security_zl7432_state", scope="session")
def vision_security_zl7432_state_fixture():
    """Load the vision security zl7432 switch node state fixture data."""
    return json.loads(load_fixture("zwave_js/vision_security_zl7432_state.json"))


@pytest.fixture(name="zen_31_state", scope="session")
def zem_31_state_fixture():
    """Load the zen_31 node state fixture data."""
    return json.loads(load_fixture("zwave_js/zen_31_state.json"))


@pytest.fixture(name="client")
def mock_client_fixture(controller_state, version_state):
    """Mock a client."""

    with patch(
        "homeassistant.components.zwave_js.ZwaveClient", autospec=True
    ) as client_class:
        client = client_class.return_value

        async def connect():
            await asyncio.sleep(0)
            client.connected = True

        async def listen(driver_ready: asyncio.Event) -> None:
            driver_ready.set()
            await asyncio.sleep(30)
            assert False, "Listen wasn't canceled!"

        async def disconnect():
            client.connected = False

        client.connect = AsyncMock(side_effect=connect)
        client.listen = AsyncMock(side_effect=listen)
        client.disconnect = AsyncMock(side_effect=disconnect)
        client.driver = Driver(client, controller_state)

        client.version = VersionInfo.from_message(version_state)
        client.ws_server_url = "ws://test:3000/zjs"

        yield client


@pytest.fixture(name="multisensor_6")
def multisensor_6_fixture(client, multisensor_6_state):
    """Mock a multisensor 6 node."""
    node = Node(client, copy.deepcopy(multisensor_6_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ecolink_door_sensor")
def legacy_binary_sensor_fixture(client, ecolink_door_sensor_state):
    """Mock a legacy_binary_sensor node."""
    node = Node(client, copy.deepcopy(ecolink_door_sensor_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="hank_binary_switch")
def hank_binary_switch_fixture(client, hank_binary_switch_state):
    """Mock a binary switch node."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="bulb_6_multi_color")
def bulb_6_multi_color_fixture(client, bulb_6_multi_color_state):
    """Mock a bulb 6 multi-color node."""
    node = Node(client, copy.deepcopy(bulb_6_multi_color_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="eaton_rf9640_dimmer")
def eaton_rf9640_dimmer_fixture(client, eaton_rf9640_dimmer_state):
    """Mock a Eaton RF9640 (V4 compatible) dimmer node."""
    node = Node(client, copy.deepcopy(eaton_rf9640_dimmer_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_schlage_be469")
def lock_schlage_be469_fixture(client, lock_schlage_be469_state):
    """Mock a schlage lock node."""
    node = Node(client, copy.deepcopy(lock_schlage_be469_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_august_pro")
def lock_august_asl03_fixture(client, lock_august_asl03_state):
    """Mock a August Pro lock node."""
    node = Node(client, copy.deepcopy(lock_august_asl03_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct100_plus")
def climate_radio_thermostat_ct100_plus_fixture(
    client, climate_radio_thermostat_ct100_plus_state
):
    """Mock a climate radio thermostat ct100 plus node."""
    node = Node(client, copy.deepcopy(climate_radio_thermostat_ct100_plus_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct100_plus_different_endpoints")
def climate_radio_thermostat_ct100_plus_different_endpoints_fixture(
    client, climate_radio_thermostat_ct100_plus_different_endpoints_state
):
    """Mock a climate radio thermostat ct100 plus node with values on different endpoints."""
    node = Node(
        client,
        copy.deepcopy(climate_radio_thermostat_ct100_plus_different_endpoints_state),
    )
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_danfoss_lc_13")
def climate_danfoss_lc_13_fixture(client, climate_danfoss_lc_13_state):
    """Mock a climate radio danfoss LC-13 node."""
    node = Node(client, copy.deepcopy(climate_danfoss_lc_13_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_eurotronic_spirit_z")
def climate_eurotronic_spirit_z_fixture(client, climate_eurotronic_spirit_z_state):
    """Mock a climate radio danfoss LC-13 node."""
    node = Node(client, climate_eurotronic_spirit_z_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm3")
def climate_heatit_z_trm3_fixture(client, climate_heatit_z_trm3_state):
    """Mock a climate radio HEATIT Z-TRM3 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm3_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nortek_thermostat")
def nortek_thermostat_fixture(client, nortek_thermostat_state):
    """Mock a nortek thermostat node."""
    node = Node(client, copy.deepcopy(nortek_thermostat_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="srt321_hrt4_zw")
def srt321_hrt4_zw_fixture(client, srt321_hrt4_zw_state):
    """Mock a HRT4-ZW / SRT321 / SRT322 thermostat node."""
    node = Node(client, copy.deepcopy(srt321_hrt4_zw_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_radiator_thermostat")
def aeotec_radiator_thermostat_fixture(client, aeotec_radiator_thermostat_state):
    """Mock a Aeotec thermostat node."""
    node = Node(client, aeotec_radiator_thermostat_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nortek_thermostat_added_event")
def nortek_thermostat_added_event_fixture(client):
    """Mock a Nortek thermostat node added event."""
    event_data = json.loads(load_fixture("zwave_js/nortek_thermostat_added_event.json"))
    event = Event("node added", event_data)
    return event


@pytest.fixture(name="nortek_thermostat_removed_event")
def nortek_thermostat_removed_event_fixture(client):
    """Mock a Nortek thermostat node removed event."""
    event_data = json.loads(
        load_fixture("zwave_js/nortek_thermostat_removed_event.json")
    )
    event = Event("node removed", event_data)
    return event


@pytest.fixture(name="integration")
async def integration_fixture(hass, client):
    """Set up the zwave_js integration."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="chain_actuator_zws12")
def window_cover_fixture(client, chain_actuator_zws12_state):
    """Mock a window cover node."""
    node = Node(client, copy.deepcopy(chain_actuator_zws12_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="in_wall_smart_fan_control")
def in_wall_smart_fan_control_fixture(client, in_wall_smart_fan_control_state):
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(in_wall_smart_fan_control_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="null_name_check")
def null_name_check_fixture(client, null_name_check_state):
    """Mock a node with no name."""
    node = Node(client, copy.deepcopy(null_name_check_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="multiple_devices")
def multiple_devices_fixture(
    client, climate_radio_thermostat_ct100_plus_state, lock_schlage_be469_state
):
    """Mock a client with multiple devices."""
    node = Node(client, copy.deepcopy(climate_radio_thermostat_ct100_plus_state))
    client.driver.controller.nodes[node.node_id] = node
    node = Node(client, copy.deepcopy(lock_schlage_be469_state))
    client.driver.controller.nodes[node.node_id] = node
    return client.driver.controller.nodes


@pytest.fixture(name="gdc_zw062")
def motorized_barrier_cover_fixture(client, gdc_zw062_state):
    """Mock a motorized barrier node."""
    node = Node(client, copy.deepcopy(gdc_zw062_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="iblinds_v2")
def iblinds_cover_fixture(client, iblinds_v2_state):
    """Mock an iBlinds v2.0 window cover node."""
    node = Node(client, copy.deepcopy(iblinds_v2_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeon_smart_switch_6")
def aeon_smart_switch_6_fixture(client, aeon_smart_switch_6_state):
    """Mock an AEON Labs (ZW096) Smart Switch 6 node."""
    node = Node(client, aeon_smart_switch_6_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ge_12730")
def ge_12730_fixture(client, ge_12730_state):
    """Mock a GE 12730 fan controller node."""
    node = Node(client, copy.deepcopy(ge_12730_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="inovelli_lzw36")
def inovelli_lzw36_fixture(client, inovelli_lzw36_state):
    """Mock a Inovelli LZW36 fan controller node."""
    node = Node(client, copy.deepcopy(inovelli_lzw36_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_id_lock_as_id150")
def lock_id_lock_as_id150(client, lock_id_lock_as_id150_state):
    """Mock an id lock id-150 lock node."""
    node = Node(client, copy.deepcopy(lock_id_lock_as_id150_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct101_multiple_temp_units")
def climate_radio_thermostat_ct101_multiple_temp_units_fixture(
    client, climate_radio_thermostat_ct101_multiple_temp_units_state
):
    """Mock a climate device with multiple temp units node."""
    node = Node(
        client, copy.deepcopy(climate_radio_thermostat_ct101_multiple_temp_units_state)
    )
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(
    name="climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints"
)
def climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_fixture(
    client,
    climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state,
):
    """Mock a climate device with mode and setpoint on differenet endpoints node."""
    node = Node(
        client,
        copy.deepcopy(
            climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state
        ),
    )
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="vision_security_zl7432")
def vision_security_zl7432_fixture(client, vision_security_zl7432_state):
    """Mock a vision security zl7432 node."""
    node = Node(client, copy.deepcopy(vision_security_zl7432_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zen_31")
def zen_31_fixture(client, zen_31_state):
    """Mock a bulb 6 multi-color node."""
    node = Node(client, copy.deepcopy(zen_31_state))
    client.driver.controller.nodes[node.node_id] = node
    return node
