"""Provide common Z-Wave JS fixtures."""
import asyncio
import copy
import io
import json
from unittest.mock import DEFAULT, AsyncMock, patch

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node
from zwave_js_server.version import VersionInfo

from homeassistant.core import HomeAssistant

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
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
        side_effect=addon_info_side_effect,
    ) as addon_info:
        addon_info.return_value = {
            "available": False,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info


@pytest.fixture(name="addon_store_info_side_effect")
def addon_store_info_side_effect_fixture():
    """Return the add-on store info side effect."""
    return None


@pytest.fixture(name="addon_store_info")
def mock_addon_store_info(addon_store_info_side_effect):
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info",
        side_effect=addon_store_info_side_effect,
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": False,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


@pytest.fixture(name="addon_running")
def mock_addon_running(addon_store_info, addon_info):
    """Mock add-on already running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "started",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["state"] = "started"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="addon_installed")
def mock_addon_installed(addon_store_info, addon_info):
    """Mock add-on already installed but not running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "stopped",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="addon_not_installed")
def mock_addon_not_installed(addon_store_info, addon_info):
    """Mock add-on not installed."""
    addon_store_info.return_value["available"] = True
    return addon_info


@pytest.fixture(name="addon_options")
def mock_addon_options(addon_info):
    """Mock add-on options."""
    return addon_info.return_value["options"]


@pytest.fixture(name="set_addon_options_side_effect")
def set_addon_options_side_effect_fixture(addon_options):
    """Return the set add-on options side effect."""

    async def set_addon_options(hass: HomeAssistant, slug, options):
        """Mock set add-on options."""
        addon_options.update(options["options"])

    return set_addon_options


@pytest.fixture(name="set_addon_options")
def mock_set_addon_options(set_addon_options_side_effect):
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_set_addon_options",
        side_effect=set_addon_options_side_effect,
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon_side_effect")
def install_addon_side_effect_fixture(addon_store_info, addon_info):
    """Return the install add-on side effect."""

    async def install_addon(hass: HomeAssistant, slug):
        """Mock install add-on."""
        addon_store_info.return_value = {
            "available": True,
            "installed": "1.0.0",
            "state": "stopped",
            "version": "1.0.0",
        }
        addon_info.return_value["available"] = True
        addon_info.return_value["state"] = "stopped"
        addon_info.return_value["version"] = "1.0.0"

    return install_addon


@pytest.fixture(name="install_addon")
def mock_install_addon(install_addon_side_effect):
    """Mock install add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon",
        side_effect=install_addon_side_effect,
    ) as install_addon:
        yield install_addon


@pytest.fixture(name="update_addon")
def mock_update_addon():
    """Mock update add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_update_addon"
    ) as update_addon:
        yield update_addon


@pytest.fixture(name="start_addon_side_effect")
def start_addon_side_effect_fixture(addon_store_info, addon_info):
    """Return the start add-on options side effect."""

    async def start_addon(hass: HomeAssistant, slug):
        """Mock start add-on."""
        addon_store_info.return_value = {
            "available": True,
            "installed": "1.0.0",
            "state": "started",
            "version": "1.0.0",
        }
        addon_info.return_value["available"] = True
        addon_info.return_value["state"] = "started"

    return start_addon


@pytest.fixture(name="start_addon")
def mock_start_addon(start_addon_side_effect):
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon",
        side_effect=start_addon_side_effect,
    ) as start_addon:
        yield start_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture():
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


@pytest.fixture(name="restart_addon_side_effect")
def restart_addon_side_effect_fixture():
    """Return the restart add-on options side effect."""
    return None


@pytest.fixture(name="restart_addon")
def mock_restart_addon(restart_addon_side_effect):
    """Mock restart add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_restart_addon",
        side_effect=restart_addon_side_effect,
    ) as restart_addon:
        yield restart_addon


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture():
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


@pytest.fixture(name="create_backup")
def create_backup_fixture():
    """Mock create backup."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_create_backup"
    ) as create_backup:
        yield create_backup


# State fixtures


@pytest.fixture(name="controller_state", scope="session")
def controller_state_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("zwave_js/controller_state.json"))


@pytest.fixture(name="controller_node_state", scope="session")
def controller_node_state_fixture():
    """Load the controller node state fixture data."""
    return json.loads(load_fixture("zwave_js/controller_node_state.json"))


@pytest.fixture(name="version_state", scope="session")
def version_state_fixture():
    """Load the version state fixture data."""
    return {
        "type": "version",
        "driverVersion": "6.0.0-beta.0",
        "serverVersion": "1.0.0",
        "homeId": 1234567890,
    }


@pytest.fixture(name="log_config_state")
def log_config_state_fixture():
    """Return log config state fixture data."""
    return {
        "enabled": True,
        "level": "info",
        "logToFile": False,
        "filename": "",
        "forceConsole": False,
    }


@pytest.fixture(name="config_entry_diagnostics", scope="session")
def config_entry_diagnostics_fixture():
    """Load the config entry diagnostics fixture data."""
    return json.loads(load_fixture("zwave_js/config_entry_diagnostics.json"))


@pytest.fixture(name="config_entry_diagnostics_redacted", scope="session")
def config_entry_diagnostics_redacted_fixture():
    """Load the redacted config entry diagnostics fixture data."""
    return json.loads(load_fixture("zwave_js/config_entry_diagnostics_redacted.json"))


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


@pytest.fixture(name="light_color_null_values_state", scope="session")
def light_color_null_values_state_fixture():
    """Load the light color null values node state fixture data."""
    return json.loads(load_fixture("zwave_js/light_color_null_values_state.json"))


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


@pytest.fixture(name="climate_adc_t3000_state", scope="session")
def climate_adc_t3000_state_fixture():
    """Load the climate ADC-T3000 node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_adc_t3000_state.json"))


@pytest.fixture(name="climate_airzone_aidoo_control_hvac_unit_state", scope="session")
def climate_airzone_aidoo_control_hvac_unit_state_fixture():
    """Load the climate Airzone Aidoo Control HVAC Unit state fixture data."""
    return json.loads(
        load_fixture("zwave_js/climate_airzone_aidoo_control_hvac_unit_state.json")
    )


@pytest.fixture(name="climate_danfoss_lc_13_state", scope="session")
def climate_danfoss_lc_13_state_fixture():
    """Load Danfoss (LC-13) electronic radiator thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_danfoss_lc_13_state.json"))


@pytest.fixture(name="climate_eurotronic_spirit_z_state", scope="session")
def climate_eurotronic_spirit_z_state_fixture():
    """Load the climate Eurotronic Spirit Z thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_eurotronic_spirit_z_state.json"))


@pytest.fixture(name="climate_heatit_z_trm3_state", scope="session")
def climate_heatit_z_trm3_state_fixture():
    """Load the climate HEATIT Z-TRM3 thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_heatit_z_trm3_state.json"))


@pytest.fixture(name="climate_heatit_z_trm2fx_state", scope="session")
def climate_heatit_z_trm2fx_state_fixture():
    """Load the climate HEATIT Z-TRM2fx thermostat node state fixture data."""
    return json.loads(load_fixture("zwave_js/climate_heatit_z_trm2fx_state.json"))


@pytest.fixture(name="climate_heatit_z_trm3_no_value_state", scope="session")
def climate_heatit_z_trm3_no_value_state_fixture():
    """Load the climate HEATIT Z-TRM3 thermostat node w/no value state fixture data."""
    return json.loads(
        load_fixture("zwave_js/climate_heatit_z_trm3_no_value_state.json")
    )


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


@pytest.fixture(name="fan_generic_state", scope="session")
def fan_generic_state_fixture():
    """Load the fan node state fixture data."""
    return json.loads(load_fixture("zwave_js/fan_generic_state.json"))


@pytest.fixture(name="hs_fc200_state", scope="session")
def hs_fc200_state_fixture():
    """Load the HS FC200+ node state fixture data."""
    return json.loads(load_fixture("zwave_js/fan_hs_fc200_state.json"))


@pytest.fixture(name="leviton_zw4sf_state", scope="session")
def leviton_zw4sf_state_fixture():
    """Load the Leviton ZW4SF node state fixture data."""
    return json.loads(load_fixture("zwave_js/leviton_zw4sf_state.json"))


@pytest.fixture(name="fan_honeywell_39358_state", scope="session")
def fan_honeywell_39358_state_fixture():
    """Load the fan node state fixture data."""
    return json.loads(load_fixture("zwave_js/fan_honeywell_39358_state.json"))


@pytest.fixture(name="gdc_zw062_state", scope="session")
def motorized_barrier_cover_state_fixture():
    """Load the motorized barrier cover node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_zw062_state.json"))


@pytest.fixture(name="iblinds_v2_state", scope="session")
def iblinds_v2_state_fixture():
    """Load the iBlinds v2 node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_iblinds_v2_state.json"))


@pytest.fixture(name="iblinds_v3_state", scope="session")
def iblinds_v3_state_fixture():
    """Load the iBlinds v3 node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_iblinds_v3_state.json"))


@pytest.fixture(name="qubino_shutter_state", scope="session")
def qubino_shutter_state_fixture():
    """Load the Qubino Shutter node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_qubino_shutter_state.json"))


@pytest.fixture(name="aeotec_nano_shutter_state", scope="session")
def aeotec_nano_shutter_state_fixture():
    """Load the Aeotec Nano Shutter node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_aeotec_nano_shutter_state.json"))


@pytest.fixture(name="fibaro_fgr222_shutter_state", scope="session")
def fibaro_fgr222_shutter_state_fixture():
    """Load the Fibaro FGR222 node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_fibaro_fgr222_state.json"))


@pytest.fixture(name="merten_507801_state", scope="session")
def merten_507801_state_fixture():
    """Load the Merten 507801 Shutter node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_merten_507801_state.json"))


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
    name=(
        "climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state"
    ),
    scope="session",
)
def climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state_fixture():
    """Load climate device w/ mode+setpoint on diff endpoints node state fixture data."""
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


@pytest.fixture(name="wallmote_central_scene_state", scope="session")
def wallmote_central_scene_state_fixture():
    """Load the wallmote central scene node state fixture data."""
    return json.loads(load_fixture("zwave_js/wallmote_central_scene_state.json"))


@pytest.fixture(name="ge_in_wall_dimmer_switch_state", scope="session")
def ge_in_wall_dimmer_switch_state_fixture():
    """Load the ge in-wall dimmer switch node state fixture data."""
    return json.loads(load_fixture("zwave_js/ge_in_wall_dimmer_switch_state.json"))


@pytest.fixture(name="aeotec_zw164_siren_state", scope="session")
def aeotec_zw164_siren_state_fixture():
    """Load the aeotec zw164 siren node state fixture data."""
    return json.loads(load_fixture("zwave_js/aeotec_zw164_siren_state.json"))


@pytest.fixture(name="lock_popp_electric_strike_lock_control_state", scope="session")
def lock_popp_electric_strike_lock_control_state_fixture():
    """Load the popp electric strike lock control node state fixture data."""
    return json.loads(
        load_fixture("zwave_js/lock_popp_electric_strike_lock_control_state.json")
    )


@pytest.fixture(name="fortrezz_ssa1_siren_state", scope="session")
def fortrezz_ssa1_siren_state_fixture():
    """Load the fortrezz ssa1 siren node state fixture data."""
    return json.loads(load_fixture("zwave_js/fortrezz_ssa1_siren_state.json"))


@pytest.fixture(name="fortrezz_ssa3_siren_state", scope="session")
def fortrezz_ssa3_siren_state_fixture():
    """Load the fortrezz ssa3 siren node state fixture data."""
    return json.loads(load_fixture("zwave_js/fortrezz_ssa3_siren_state.json"))


@pytest.fixture(name="zp3111_not_ready_state", scope="session")
def zp3111_not_ready_state_fixture():
    """Load the zp3111 4-in-1 sensor not-ready node state fixture data."""
    return json.loads(load_fixture("zwave_js/zp3111-5_not_ready_state.json"))


@pytest.fixture(name="zp3111_state", scope="session")
def zp3111_state_fixture():
    """Load the zp3111 4-in-1 sensor node state fixture data."""
    return json.loads(load_fixture("zwave_js/zp3111-5_state.json"))


@pytest.fixture(name="express_controls_ezmultipli_state", scope="session")
def light_express_controls_ezmultipli_state_fixture():
    """Load the Express Controls EZMultiPli node state fixture data."""
    return json.loads(load_fixture("zwave_js/express_controls_ezmultipli_state.json"))


@pytest.fixture(name="lock_home_connect_620_state", scope="session")
def lock_home_connect_620_state_fixture():
    """Load the Home Connect 620 lock node state fixture data."""
    return json.loads(load_fixture("zwave_js/lock_home_connect_620_state.json"))


@pytest.fixture(name="switch_zooz_zen72_state", scope="session")
def switch_zooz_zen72_state_fixture():
    """Load the Zooz Zen72 switch node state fixture data."""
    return json.loads(load_fixture("zwave_js/switch_zooz_zen72_state.json"))


@pytest.fixture(name="indicator_test_state", scope="session")
def indicator_test_state_fixture():
    """Load the indicator CC test node state fixture data."""
    return json.loads(load_fixture("zwave_js/indicator_test_state.json"))


@pytest.fixture(name="energy_production_state", scope="session")
def energy_production_state_fixture():
    """Load a mock node with energy production CC state fixture data."""
    return json.loads(load_fixture("zwave_js/energy_production_state.json"))


@pytest.fixture(name="nice_ibt4zwave_state", scope="session")
def nice_ibt4zwave_state_fixture():
    """Load a Nice IBT4ZWAVE cover node state fixture data."""
    return json.loads(load_fixture("zwave_js/cover_nice_ibt4zwave_state.json"))


# model fixtures


SETUP_COMMAND_RESPONSES = {
    "node.has_device_config_changed": {"result": {"changed": False}},
    "controller.get_available_firmware_updates": {
        "result": {"success": True, "status": 255}
    },
}


@pytest.fixture(name="client")
def mock_client_fixture(
    controller_state, controller_node_state, version_state, log_config_state
):
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
            listen_block = asyncio.Event()
            await listen_block.wait()
            pytest.fail("Listen wasn't canceled!")

        async def disconnect():
            client.connected = False

        client.connect = AsyncMock(side_effect=connect)
        client.listen = AsyncMock(side_effect=listen)
        client.disconnect = AsyncMock(side_effect=disconnect)
        client.driver = Driver(
            client, copy.deepcopy(controller_state), copy.deepcopy(log_config_state)
        )
        node = Node(client, copy.deepcopy(controller_node_state))
        client.driver.controller.nodes[node.node_id] = node

        client.version = VersionInfo.from_message(version_state)
        client.ws_server_url = "ws://test:3000/zjs"

        async def async_send_command_side_effect(message, require_schema=None):
            """Return the command response."""
            if resp := SETUP_COMMAND_RESPONSES.get(message["command"]):
                return resp
            return DEFAULT

        client.async_send_command.return_value = {
            "result": {"success": True, "status": 255}
        }
        client.async_send_command.side_effect = async_send_command_side_effect

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


@pytest.fixture(name="light_color_null_values")
def light_color_null_values_fixture(client, light_color_null_values_state):
    """Mock a node with current color value item being null."""
    node = Node(client, copy.deepcopy(light_color_null_values_state))
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
    """Mock climate radio thermostat ct100 plus node w/ values on diff endpoints."""
    node = Node(
        client,
        copy.deepcopy(climate_radio_thermostat_ct100_plus_different_endpoints_state),
    )
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000")
def climate_adc_t3000_fixture(client, climate_adc_t3000_state):
    """Mock a climate ADC-T3000 node."""
    node = Node(client, copy.deepcopy(climate_adc_t3000_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000_missing_setpoint")
def climate_adc_t3000_missing_setpoint_fixture(client, climate_adc_t3000_state):
    """Mock a climate ADC-T3000 node with missing de-humidify setpoint."""
    data = copy.deepcopy(climate_adc_t3000_state)
    data["name"] = f"{data['name']} missing setpoint"
    for value in data["values"][:]:
        if (
            value["commandClassName"] == "Humidity Control Setpoint"
            and value["propertyKeyName"] == "De-humidifier"
        ):
            data["values"].remove(value)
    node = Node(client, data)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000_missing_mode")
def climate_adc_t3000_missing_mode_fixture(client, climate_adc_t3000_state):
    """Mock a climate ADC-T3000 node with missing mode setpoint."""
    data = copy.deepcopy(climate_adc_t3000_state)
    data["name"] = f"{data['name']} missing mode"
    for value in data["values"]:
        if value["commandClassName"] == "Humidity Control Mode":
            states = value["metadata"]["states"]
            for key in list(states.keys()):
                if states[key] == "De-humidify":
                    del states[key]
    node = Node(client, data)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000_missing_fan_mode_states")
def climate_adc_t3000_missing_fan_mode_states_fixture(client, climate_adc_t3000_state):
    """Mock ADC-T3000 node w/ missing 'states' metadata on Thermostat Fan Mode."""
    data = copy.deepcopy(climate_adc_t3000_state)
    data["name"] = f"{data['name']} missing fan mode states"
    for value in data["values"]:
        if (
            value["commandClassName"] == "Thermostat Fan Mode"
            and value["property"] == "mode"
        ):
            del value["metadata"]["states"]
    node = Node(client, data)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_airzone_aidoo_control_hvac_unit")
def climate_airzone_aidoo_control_hvac_unit_fixture(
    client, climate_airzone_aidoo_control_hvac_unit_state
):
    """Mock a climate Airzone Aidoo Control HVAC node."""
    node = Node(client, copy.deepcopy(climate_airzone_aidoo_control_hvac_unit_state))
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


@pytest.fixture(name="climate_heatit_z_trm3_no_value")
def climate_heatit_z_trm3_no_value_fixture(
    client, climate_heatit_z_trm3_no_value_state
):
    """Mock a climate radio HEATIT Z-TRM3 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm3_no_value_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm3")
def climate_heatit_z_trm3_fixture(client, climate_heatit_z_trm3_state):
    """Mock a climate radio HEATIT Z-TRM3 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm3_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm2fx")
def climate_heatit_z_trm2fx_fixture(client, climate_heatit_z_trm2fx_state):
    """Mock a climate radio HEATIT Z-TRM2fx node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm2fx_state))
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
async def integration_fixture(hass: HomeAssistant, client):
    """Set up the zwave_js integration."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client.async_send_command.reset_mock()

    return entry


@pytest.fixture(name="chain_actuator_zws12")
def window_cover_fixture(client, chain_actuator_zws12_state):
    """Mock a window cover node."""
    node = Node(client, copy.deepcopy(chain_actuator_zws12_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fan_generic")
def fan_generic_fixture(client, fan_generic_state):
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(fan_generic_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="hs_fc200")
def hs_fc200_fixture(client, hs_fc200_state):
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(hs_fc200_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="leviton_zw4sf")
def leviton_zw4sf_fixture(client, leviton_zw4sf_state):
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(leviton_zw4sf_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fan_honeywell_39358")
def fan_honeywell_39358_fixture(client, fan_honeywell_39358_state):
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(fan_honeywell_39358_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="null_name_check")
def null_name_check_fixture(client, null_name_check_state):
    """Mock a node with no name."""
    node = Node(client, copy.deepcopy(null_name_check_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="gdc_zw062")
def motorized_barrier_cover_fixture(client, gdc_zw062_state):
    """Mock a motorized barrier node."""
    node = Node(client, copy.deepcopy(gdc_zw062_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="iblinds_v2")
def iblinds_v2_cover_fixture(client, iblinds_v2_state):
    """Mock an iBlinds v2.0 window cover node."""
    node = Node(client, copy.deepcopy(iblinds_v2_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="iblinds_v3")
def iblinds_v3_cover_fixture(client, iblinds_v3_state):
    """Mock an iBlinds v3 window cover node."""
    node = Node(client, copy.deepcopy(iblinds_v3_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="qubino_shutter")
def qubino_shutter_cover_fixture(client, qubino_shutter_state):
    """Mock a Qubino flush shutter node."""
    node = Node(client, copy.deepcopy(qubino_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_nano_shutter")
def aeotec_nano_shutter_cover_fixture(client, aeotec_nano_shutter_state):
    """Mock a Aeotec Nano Shutter node."""
    node = Node(client, copy.deepcopy(aeotec_nano_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fibaro_fgr222_shutter")
def fibaro_fgr222_shutter_cover_fixture(client, fibaro_fgr222_shutter_state):
    """Mock a Fibaro FGR222 Shutter node."""
    node = Node(client, copy.deepcopy(fibaro_fgr222_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="merten_507801")
def merten_507801_cover_fixture(client, merten_507801_state):
    """Mock a Merten 507801 Shutter node."""
    node = Node(client, copy.deepcopy(merten_507801_state))
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


@pytest.fixture(name="lock_id_lock_as_id150_not_ready")
def node_not_ready(client, lock_id_lock_as_id150_state):
    """Mock an id lock id-150 lock node that's not ready."""
    state = copy.deepcopy(lock_id_lock_as_id150_state)
    state["ready"] = False
    node = Node(client, state)
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


@pytest.fixture(name="wallmote_central_scene")
def wallmote_central_scene_fixture(client, wallmote_central_scene_state):
    """Mock a wallmote central scene node."""
    node = Node(client, copy.deepcopy(wallmote_central_scene_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ge_in_wall_dimmer_switch")
def ge_in_wall_dimmer_switch_fixture(client, ge_in_wall_dimmer_switch_state):
    """Mock a ge in-wall dimmer switch scene node."""
    node = Node(client, copy.deepcopy(ge_in_wall_dimmer_switch_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_zw164_siren")
def aeotec_zw164_siren_fixture(client, aeotec_zw164_siren_state):
    """Mock a aeotec zw164 siren node."""
    node = Node(client, copy.deepcopy(aeotec_zw164_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_popp_electric_strike_lock_control")
def lock_popp_electric_strike_lock_control_fixture(
    client, lock_popp_electric_strike_lock_control_state
):
    """Mock a popp electric strike lock control node."""
    node = Node(client, copy.deepcopy(lock_popp_electric_strike_lock_control_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fortrezz_ssa1_siren")
def fortrezz_ssa1_siren_fixture(client, fortrezz_ssa1_siren_state):
    """Mock a fortrezz ssa1 siren node."""
    node = Node(client, copy.deepcopy(fortrezz_ssa1_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fortrezz_ssa3_siren")
def fortrezz_ssa3_siren_fixture(client, fortrezz_ssa3_siren_state):
    """Mock a fortrezz ssa3 siren node."""
    node = Node(client, copy.deepcopy(fortrezz_ssa3_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="firmware_file")
def firmware_file_fixture():
    """Return mock firmware file stream."""
    return io.BytesIO(bytes(10))


@pytest.fixture(name="zp3111_not_ready")
def zp3111_not_ready_fixture(client, zp3111_not_ready_state):
    """Mock a zp3111 4-in-1 sensor node in a not-ready state."""
    node = Node(client, copy.deepcopy(zp3111_not_ready_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zp3111")
def zp3111_fixture(client, zp3111_state):
    """Mock a zp3111 4-in-1 sensor node."""
    node = Node(client, copy.deepcopy(zp3111_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="express_controls_ezmultipli")
def express_controls_ezmultipli_fixture(client, express_controls_ezmultipli_state):
    """Mock a Express Controls EZMultiPli node."""
    node = Node(client, copy.deepcopy(express_controls_ezmultipli_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_home_connect_620")
def lock_home_connect_620_fixture(client, lock_home_connect_620_state):
    """Mock a Home Connect 620 lock node."""
    node = Node(client, copy.deepcopy(lock_home_connect_620_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="switch_zooz_zen72")
def switch_zooz_zen72_fixture(client, switch_zooz_zen72_state):
    """Mock a Zooz Zen72 switch node."""
    node = Node(client, copy.deepcopy(switch_zooz_zen72_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="indicator_test")
def indicator_test_fixture(client, indicator_test_state):
    """Mock a indicator CC test node."""
    node = Node(client, copy.deepcopy(indicator_test_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="energy_production")
def energy_production_fixture(client, energy_production_state):
    """Mock a mock node with Energy Production CC."""
    node = Node(client, copy.deepcopy(energy_production_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nice_ibt4zwave")
def nice_ibt4zwave_fixture(client, nice_ibt4zwave_state):
    """Mock a Nice IBT4ZWAVE cover node."""
    node = Node(client, copy.deepcopy(nice_ibt4zwave_state))
    client.driver.controller.nodes[node.node_id] = node
    return node
