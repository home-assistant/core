"""Provide common Z-Wave JS fixtures."""

import asyncio
import copy
import io
from typing import Any, cast
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node
from zwave_js_server.model.node.data_model import NodeDataType
from zwave_js_server.version import VersionInfo

from homeassistant.components.zwave_js import PLATFORMS
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

# State fixtures


@pytest.fixture(name="controller_state", scope="package")
def controller_state_fixture() -> dict[str, Any]:
    """Load the controller state fixture data."""
    return load_json_object_fixture("controller_state.json", DOMAIN)


@pytest.fixture(name="controller_node_state", scope="package")
def controller_node_state_fixture() -> dict[str, Any]:
    """Load the controller node state fixture data."""
    return load_json_object_fixture("controller_node_state.json", DOMAIN)


@pytest.fixture(name="version_state", scope="package")
def version_state_fixture() -> dict[str, Any]:
    """Load the version state fixture data."""
    return {
        "type": "version",
        "driverVersion": "6.0.0-beta.0",
        "serverVersion": "1.0.0",
        "homeId": 1234567890,
    }


@pytest.fixture(name="log_config_state")
def log_config_state_fixture() -> dict[str, Any]:
    """Return log config state fixture data."""
    return {
        "enabled": True,
        "level": "info",
        "logToFile": False,
        "filename": "",
        "forceConsole": False,
    }


@pytest.fixture(name="config_entry_diagnostics", scope="package")
def config_entry_diagnostics_fixture() -> JsonArrayType:
    """Load the config entry diagnostics fixture data."""
    return load_json_array_fixture("config_entry_diagnostics.json", DOMAIN)


@pytest.fixture(name="config_entry_diagnostics_redacted", scope="package")
def config_entry_diagnostics_redacted_fixture() -> dict[str, Any]:
    """Load the redacted config entry diagnostics fixture data."""
    return load_json_object_fixture("config_entry_diagnostics_redacted.json", DOMAIN)


@pytest.fixture(name="multisensor_6_state", scope="package")
def multisensor_6_state_fixture() -> dict[str, Any]:
    """Load the multisensor 6 node state fixture data."""
    return load_json_object_fixture("multisensor_6_state.json", DOMAIN)


@pytest.fixture(name="ecolink_door_sensor_state", scope="package")
def ecolink_door_sensor_state_fixture() -> dict[str, Any]:
    """Load the Ecolink Door/Window Sensor node state fixture data."""
    return load_json_object_fixture("ecolink_door_sensor_state.json", DOMAIN)


@pytest.fixture(name="hank_binary_switch_state", scope="package")
def binary_switch_state_fixture() -> dict[str, Any]:
    """Load the hank binary switch node state fixture data."""
    return load_json_object_fixture("hank_binary_switch_state.json", DOMAIN)


@pytest.fixture(name="bulb_6_multi_color_state", scope="package")
def bulb_6_multi_color_state_fixture() -> dict[str, Any]:
    """Load the bulb 6 multi-color node state fixture data."""
    return load_json_object_fixture("bulb_6_multi_color_state.json", DOMAIN)


@pytest.fixture(name="light_color_null_values_state", scope="package")
def light_color_null_values_state_fixture() -> dict[str, Any]:
    """Load the light color null values node state fixture data."""
    return load_json_object_fixture("light_color_null_values_state.json", DOMAIN)


@pytest.fixture(name="eaton_rf9640_dimmer_state", scope="package")
def eaton_rf9640_dimmer_state_fixture() -> dict[str, Any]:
    """Load the eaton rf9640 dimmer node state fixture data."""
    return load_json_object_fixture("eaton_rf9640_dimmer_state.json", DOMAIN)


@pytest.fixture(name="lock_schlage_be469_state", scope="package")
def lock_schlage_be469_state_fixture() -> dict[str, Any]:
    """Load the schlage lock node state fixture data."""
    return load_json_object_fixture("lock_schlage_be469_state.json", DOMAIN)


@pytest.fixture(name="lock_august_asl03_state", scope="package")
def lock_august_asl03_state_fixture() -> dict[str, Any]:
    """Load the August Pro lock node state fixture data."""
    return load_json_object_fixture("lock_august_asl03_state.json", DOMAIN)


@pytest.fixture(name="climate_radio_thermostat_ct100_plus_state", scope="package")
def climate_radio_thermostat_ct100_plus_state_fixture() -> dict[str, Any]:
    """Load the climate radio thermostat ct100 plus node state fixture data."""
    return load_json_object_fixture(
        "climate_radio_thermostat_ct100_plus_state.json", DOMAIN
    )


@pytest.fixture(
    name="climate_radio_thermostat_ct100_plus_different_endpoints_state",
    scope="package",
)
def climate_radio_thermostat_ct100_plus_different_endpoints_state_fixture() -> dict[
    str, Any
]:
    """Load the thermostat fixture state with values on different endpoints.

    This device is a radio thermostat ct100.
    """
    return load_json_object_fixture(
        "climate_radio_thermostat_ct100_plus_different_endpoints_state.json", DOMAIN
    )


@pytest.fixture(name="climate_adc_t3000_state", scope="package")
def climate_adc_t3000_state_fixture() -> dict[str, Any]:
    """Load the climate ADC-T3000 node state fixture data."""
    return load_json_object_fixture("climate_adc_t3000_state.json", DOMAIN)


@pytest.fixture(name="climate_airzone_aidoo_control_hvac_unit_state", scope="package")
def climate_airzone_aidoo_control_hvac_unit_state_fixture() -> dict[str, Any]:
    """Load the climate Airzone Aidoo Control HVAC Unit state fixture data."""
    return load_json_object_fixture(
        "climate_airzone_aidoo_control_hvac_unit_state.json", DOMAIN
    )


@pytest.fixture(name="climate_danfoss_lc_13_state", scope="package")
def climate_danfoss_lc_13_state_fixture() -> dict[str, Any]:
    """Load Danfoss (LC-13) electronic radiator thermostat node state fixture data."""
    return load_json_object_fixture("climate_danfoss_lc_13_state.json", DOMAIN)


@pytest.fixture(name="climate_eurotronic_spirit_z_state", scope="package")
def climate_eurotronic_spirit_z_state_fixture() -> dict[str, Any]:
    """Load the climate Eurotronic Spirit Z thermostat node state fixture data."""
    return load_json_object_fixture("climate_eurotronic_spirit_z_state.json", DOMAIN)


@pytest.fixture(name="climate_heatit_z_trm6_state", scope="package")
def climate_heatit_z_trm6_state_fixture() -> dict[str, Any]:
    """Load the climate HEATIT Z-TRM6 thermostat node state fixture data."""
    return load_json_object_fixture("climate_heatit_z_trm6_state.json", DOMAIN)


@pytest.fixture(name="climate_heatit_z_trm3_state", scope="package")
def climate_heatit_z_trm3_state_fixture() -> dict[str, Any]:
    """Load the climate HEATIT Z-TRM3 thermostat node state fixture data."""
    return load_json_object_fixture("climate_heatit_z_trm3_state.json", DOMAIN)


@pytest.fixture(name="climate_heatit_z_trm2fx_state", scope="package")
def climate_heatit_z_trm2fx_state_fixture() -> dict[str, Any]:
    """Load the climate HEATIT Z-TRM2fx thermostat node state fixture data."""
    return load_json_object_fixture("climate_heatit_z_trm2fx_state.json", DOMAIN)


@pytest.fixture(name="climate_heatit_z_trm3_no_value_state", scope="package")
def climate_heatit_z_trm3_no_value_state_fixture() -> dict[str, Any]:
    """Load the climate HEATIT Z-TRM3 thermostat node w/no value state fixture data."""
    return load_json_object_fixture("climate_heatit_z_trm3_no_value_state.json", DOMAIN)


@pytest.fixture(name="nortek_thermostat_state", scope="package")
def nortek_thermostat_state_fixture() -> dict[str, Any]:
    """Load the nortek thermostat node state fixture data."""
    return load_json_object_fixture("nortek_thermostat_state.json", DOMAIN)


@pytest.fixture(name="srt321_hrt4_zw_state", scope="package")
def srt321_hrt4_zw_state_fixture() -> dict[str, Any]:
    """Load the climate HRT4-ZW / SRT321 / SRT322 thermostat node state fixture data."""
    return load_json_object_fixture("srt321_hrt4_zw_state.json", DOMAIN)


@pytest.fixture(name="chain_actuator_zws12_state", scope="package")
def window_cover_state_fixture() -> dict[str, Any]:
    """Load the window cover node state fixture data."""
    return load_json_object_fixture("chain_actuator_zws12_state.json", DOMAIN)


@pytest.fixture(name="fan_generic_state", scope="package")
def fan_generic_state_fixture() -> dict[str, Any]:
    """Load the fan node state fixture data."""
    return load_json_object_fixture("fan_generic_state.json", DOMAIN)


@pytest.fixture(name="hs_fc200_state", scope="package")
def hs_fc200_state_fixture() -> dict[str, Any]:
    """Load the HS FC200+ node state fixture data."""
    return load_json_object_fixture("fan_hs_fc200_state.json", DOMAIN)


@pytest.fixture(name="leviton_zw4sf_state", scope="package")
def leviton_zw4sf_state_fixture() -> dict[str, Any]:
    """Load the Leviton ZW4SF node state fixture data."""
    return load_json_object_fixture("leviton_zw4sf_state.json", DOMAIN)


@pytest.fixture(name="fan_honeywell_39358_state", scope="package")
def fan_honeywell_39358_state_fixture() -> dict[str, Any]:
    """Load the fan node state fixture data."""
    return load_json_object_fixture("fan_honeywell_39358_state.json", DOMAIN)


@pytest.fixture(name="gdc_zw062_state", scope="package")
def motorized_barrier_cover_state_fixture() -> dict[str, Any]:
    """Load the motorized barrier cover node state fixture data."""
    return load_json_object_fixture("cover_zw062_state.json", DOMAIN)


@pytest.fixture(name="iblinds_v2_state", scope="package")
def iblinds_v2_state_fixture() -> dict[str, Any]:
    """Load the iBlinds v2 node state fixture data."""
    return load_json_object_fixture("cover_iblinds_v2_state.json", DOMAIN)


@pytest.fixture(name="iblinds_v3_state", scope="package")
def iblinds_v3_state_fixture() -> dict[str, Any]:
    """Load the iBlinds v3 node state fixture data."""
    return load_json_object_fixture("cover_iblinds_v3_state.json", DOMAIN)


@pytest.fixture(name="zvidar_state", scope="package")
def zvidar_state_fixture() -> dict[str, Any]:
    """Load the ZVIDAR node state fixture data."""
    return load_json_object_fixture("cover_zvidar_state.json", DOMAIN)


@pytest.fixture(name="qubino_shutter_state", scope="package")
def qubino_shutter_state_fixture() -> dict[str, Any]:
    """Load the Qubino Shutter node state fixture data."""
    return load_json_object_fixture("cover_qubino_shutter_state.json", DOMAIN)


@pytest.fixture(name="aeotec_nano_shutter_state", scope="package")
def aeotec_nano_shutter_state_fixture() -> dict[str, Any]:
    """Load the Aeotec Nano Shutter node state fixture data."""
    return load_json_object_fixture("cover_aeotec_nano_shutter_state.json", DOMAIN)


@pytest.fixture(name="fibaro_fgr222_shutter_state", scope="package")
def fibaro_fgr222_shutter_state_fixture() -> dict[str, Any]:
    """Load the Fibaro FGR222 node state fixture data."""
    return load_json_object_fixture("cover_fibaro_fgr222_state.json", DOMAIN)


@pytest.fixture(name="fibaro_fgr223_shutter_state", scope="package")
def fibaro_fgr223_shutter_state_fixture() -> dict[str, Any]:
    """Load the Fibaro FGR223 node state fixture data."""
    return load_json_object_fixture("cover_fibaro_fgr223_state.json", DOMAIN)


@pytest.fixture(name="shelly_europe_ltd_qnsh_001p10_state", scope="package")
def shelly_europe_ltd_qnsh_001p10_state_fixture() -> dict[str, Any]:
    """Load the Shelly QNSH 001P10 node state fixture data."""
    return load_json_object_fixture("shelly_europe_ltd_qnsh_001p10_state.json", DOMAIN)


@pytest.fixture(name="merten_507801_state", scope="package")
def merten_507801_state_fixture() -> dict[str, Any]:
    """Load the Merten 507801 Shutter node state fixture data."""
    return load_json_object_fixture("cover_merten_507801_state.json", DOMAIN)


@pytest.fixture(name="aeon_smart_switch_6_state", scope="package")
def aeon_smart_switch_6_state_fixture() -> dict[str, Any]:
    """Load the AEON Labs (ZW096) Smart Switch 6 node state fixture data."""
    return load_json_object_fixture("aeon_smart_switch_6_state.json", DOMAIN)


@pytest.fixture(name="ge_12730_state", scope="package")
def ge_12730_state_fixture() -> dict[str, Any]:
    """Load the GE 12730 node state fixture data."""
    return load_json_object_fixture("fan_ge_12730_state.json", DOMAIN)


@pytest.fixture(name="aeotec_radiator_thermostat_state", scope="package")
def aeotec_radiator_thermostat_state_fixture() -> dict[str, Any]:
    """Load the Aeotec Radiator Thermostat node state fixture data."""
    return load_json_object_fixture("aeotec_radiator_thermostat_state.json", DOMAIN)


@pytest.fixture(name="inovelli_lzw36_state", scope="package")
def inovelli_lzw36_state_fixture() -> dict[str, Any]:
    """Load the Inovelli LZW36 node state fixture data."""
    return load_json_object_fixture("inovelli_lzw36_state.json", DOMAIN)


@pytest.fixture(name="null_name_check_state", scope="package")
def null_name_check_state_fixture() -> dict[str, Any]:
    """Load the null name check node state fixture data."""
    return load_json_object_fixture("null_name_check_state.json", DOMAIN)


@pytest.fixture(name="lock_id_lock_as_id150_state", scope="package")
def lock_id_lock_as_id150_state_fixture() -> dict[str, Any]:
    """Load the id lock id-150 lock node state fixture data."""
    return load_json_object_fixture("lock_id_lock_as_id150_state.json", DOMAIN)


@pytest.fixture(
    name="climate_radio_thermostat_ct101_multiple_temp_units_state", scope="package"
)
def climate_radio_thermostat_ct101_multiple_temp_units_state_fixture() -> dict[
    str, Any
]:
    """Load the climate multiple temp units node state fixture data."""
    return load_json_object_fixture(
        "climate_radio_thermostat_ct101_multiple_temp_units_state.json", DOMAIN
    )


@pytest.fixture(
    name=(
        "climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state"
    ),
    scope="package",
)
def climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state_fixture() -> (
    dict[str, Any]
):
    """Load climate device w/ mode+setpoint on diff endpoints node state fixture data."""
    return load_json_object_fixture(
        "climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints_state.json",
        DOMAIN,
    )


@pytest.fixture(name="vision_security_zl7432_state", scope="package")
def vision_security_zl7432_state_fixture() -> dict[str, Any]:
    """Load the vision security zl7432 switch node state fixture data."""
    return load_json_object_fixture("vision_security_zl7432_state.json", DOMAIN)


@pytest.fixture(name="zen_31_state", scope="package")
def zem_31_state_fixture() -> dict[str, Any]:
    """Load the zen_31 node state fixture data."""
    return load_json_object_fixture("zen_31_state.json", DOMAIN)


@pytest.fixture(name="wallmote_central_scene_state", scope="package")
def wallmote_central_scene_state_fixture() -> dict[str, Any]:
    """Load the wallmote central scene node state fixture data."""
    return load_json_object_fixture("wallmote_central_scene_state.json", DOMAIN)


@pytest.fixture(name="ge_in_wall_dimmer_switch_state", scope="package")
def ge_in_wall_dimmer_switch_state_fixture() -> dict[str, Any]:
    """Load the ge in-wall dimmer switch node state fixture data."""
    return load_json_object_fixture("ge_in_wall_dimmer_switch_state.json", DOMAIN)


@pytest.fixture(name="aeotec_zw164_siren_state", scope="package")
def aeotec_zw164_siren_state_fixture() -> dict[str, Any]:
    """Load the aeotec zw164 siren node state fixture data."""
    return load_json_object_fixture("aeotec_zw164_siren_state.json", DOMAIN)


@pytest.fixture(name="lock_popp_electric_strike_lock_control_state", scope="package")
def lock_popp_electric_strike_lock_control_state_fixture() -> dict[str, Any]:
    """Load the popp electric strike lock control node state fixture data."""
    return load_json_object_fixture(
        "lock_popp_electric_strike_lock_control_state.json", DOMAIN
    )


@pytest.fixture(name="fortrezz_ssa1_siren_state", scope="package")
def fortrezz_ssa1_siren_state_fixture() -> dict[str, Any]:
    """Load the fortrezz ssa1 siren node state fixture data."""
    return load_json_object_fixture("fortrezz_ssa1_siren_state.json", DOMAIN)


@pytest.fixture(name="fortrezz_ssa3_siren_state", scope="package")
def fortrezz_ssa3_siren_state_fixture() -> dict[str, Any]:
    """Load the fortrezz ssa3 siren node state fixture data."""
    return load_json_object_fixture("fortrezz_ssa3_siren_state.json", DOMAIN)


@pytest.fixture(name="zp3111_not_ready_state", scope="package")
def zp3111_not_ready_state_fixture() -> dict[str, Any]:
    """Load the zp3111 4-in-1 sensor not-ready node state fixture data."""
    return load_json_object_fixture("zp3111-5_not_ready_state.json", DOMAIN)


@pytest.fixture(name="zp3111_state", scope="package")
def zp3111_state_fixture() -> dict[str, Any]:
    """Load the zp3111 4-in-1 sensor node state fixture data."""
    return load_json_object_fixture("zp3111-5_state.json", DOMAIN)


@pytest.fixture(name="express_controls_ezmultipli_state", scope="package")
def light_express_controls_ezmultipli_state_fixture() -> dict[str, Any]:
    """Load the Express Controls EZMultiPli node state fixture data."""
    return load_json_object_fixture("express_controls_ezmultipli_state.json", DOMAIN)


@pytest.fixture(name="lock_home_connect_620_state", scope="package")
def lock_home_connect_620_state_fixture() -> dict[str, Any]:
    """Load the Home Connect 620 lock node state fixture data."""
    return load_json_object_fixture("lock_home_connect_620_state.json", DOMAIN)


@pytest.fixture(name="switch_zooz_zen72_state", scope="package")
def switch_zooz_zen72_state_fixture() -> dict[str, Any]:
    """Load the Zooz Zen72 switch node state fixture data."""
    return load_json_object_fixture("switch_zooz_zen72_state.json", DOMAIN)


@pytest.fixture(name="indicator_test_state", scope="package")
def indicator_test_state_fixture() -> dict[str, Any]:
    """Load the indicator CC test node state fixture data."""
    return load_json_object_fixture("indicator_test_state.json", DOMAIN)


@pytest.fixture(name="energy_production_state", scope="package")
def energy_production_state_fixture() -> dict[str, Any]:
    """Load a mock node with energy production CC state fixture data."""
    return load_json_object_fixture("energy_production_state.json", DOMAIN)


@pytest.fixture(name="nice_ibt4zwave_state", scope="package")
def nice_ibt4zwave_state_fixture() -> dict[str, Any]:
    """Load a Nice IBT4ZWAVE cover node state fixture data."""
    return load_json_object_fixture("cover_nice_ibt4zwave_state.json", DOMAIN)


@pytest.fixture(name="logic_group_zdb5100_state", scope="package")
def logic_group_zdb5100_state_fixture() -> dict[str, Any]:
    """Load the Logic Group ZDB5100 node state fixture data."""
    return load_json_object_fixture("logic_group_zdb5100_state.json", DOMAIN)


@pytest.fixture(name="central_scene_node_state", scope="package")
def central_scene_node_state_fixture() -> dict[str, Any]:
    """Load node with Central Scene CC node state fixture data."""
    return load_json_object_fixture("central_scene_node_state.json", DOMAIN)


@pytest.fixture(name="light_device_class_is_null_state", scope="package")
def light_device_class_is_null_state_fixture() -> dict[str, Any]:
    """Load node with device class is None state fixture data."""
    return load_json_object_fixture("light_device_class_is_null_state.json", DOMAIN)


@pytest.fixture(name="basic_cc_sensor_state", scope="package")
def basic_cc_sensor_state_fixture() -> dict[str, Any]:
    """Load node with Basic CC sensor fixture data."""
    return load_json_object_fixture("basic_cc_sensor_state.json", DOMAIN)


@pytest.fixture(name="window_covering_outbound_bottom_state", scope="package")
def window_covering_outbound_bottom_state_fixture() -> dict[str, Any]:
    """Load node with Window Covering CC fixture data, with only the outbound bottom position supported."""
    return load_json_object_fixture("window_covering_outbound_bottom.json", DOMAIN)


@pytest.fixture(name="siren_neo_coolcam_state")
def siren_neo_coolcam_state_state_fixture() -> NodeDataType:
    """Load node with siren_neo_coolcam_state fixture data."""
    return cast(
        NodeDataType,
        load_json_object_fixture("siren_neo_coolcam_nas-ab01z_state.json", DOMAIN),
    )


@pytest.fixture(name="aeotec_smart_switch_7_state")
def aeotec_smart_switch_7_state_fixture() -> NodeDataType:
    """Load node with fixture data for Aeotec Smart Switch 7."""
    return cast(
        NodeDataType,
        load_json_object_fixture("aeotec_smart_switch_7_state.json", DOMAIN),
    )


@pytest.fixture(name="zcombo_smoke_co_alarm_state")
def zcombo_smoke_co_alarm_state_fixture() -> NodeDataType:
    """Load node with fixture data for ZCombo-G Smoke/CO Alarm."""
    return cast(
        NodeDataType,
        load_json_object_fixture("zcombo_smoke_co_alarm_state.json", DOMAIN),
    )


# model fixtures


@pytest.fixture(name="listen_block")
def mock_listen_block_fixture() -> asyncio.Event:
    """Mock a listen block."""
    return asyncio.Event()


@pytest.fixture(name="listen_result")
def listen_result_fixture() -> asyncio.Future[None]:
    """Mock a listen result."""
    return asyncio.Future()


@pytest.fixture(name="client")
def mock_client_fixture(
    controller_state: dict[str, Any],
    controller_node_state: dict[str, Any],
    version_state: dict[str, Any],
    log_config_state: dict[str, Any],
    listen_block: asyncio.Event,
    listen_result: asyncio.Future[None],
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
            await listen_block.wait()
            await listen_result

        async def disconnect():
            client.connected = False

        client.connect = AsyncMock(side_effect=connect)
        client.listen = AsyncMock(side_effect=listen)
        client.disconnect = AsyncMock(side_effect=disconnect)
        client.disable_server_logging = MagicMock()
        client.driver = Driver(
            client, copy.deepcopy(controller_state), copy.deepcopy(log_config_state)
        )
        node = Node(client, copy.deepcopy(controller_node_state))
        client.driver.controller.nodes[node.node_id] = node

        client.version = VersionInfo.from_message(version_state)
        client.ws_server_url = "ws://test:3000/zjs"

        async def async_send_command_side_effect(message, require_schema=None):
            """Return the command response."""
            if message["command"] == "node.has_device_config_changed":
                return {"changed": False}
            return DEFAULT

        client.async_send_command.return_value = {
            "result": {"success": True, "status": 255}
        }
        client.async_send_command.side_effect = async_send_command_side_effect

        yield client


@pytest.fixture(name="multisensor_6")
def multisensor_6_fixture(client, multisensor_6_state) -> Node:
    """Mock a multisensor 6 node."""
    node = Node(client, copy.deepcopy(multisensor_6_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ecolink_door_sensor")
def legacy_binary_sensor_fixture(client, ecolink_door_sensor_state) -> Node:
    """Mock a legacy_binary_sensor node."""
    node = Node(client, copy.deepcopy(ecolink_door_sensor_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="hank_binary_switch")
def hank_binary_switch_fixture(client, hank_binary_switch_state) -> Node:
    """Mock a binary switch node."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="bulb_6_multi_color")
def bulb_6_multi_color_fixture(client, bulb_6_multi_color_state) -> Node:
    """Mock a bulb 6 multi-color node."""
    node = Node(client, copy.deepcopy(bulb_6_multi_color_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="light_color_null_values")
def light_color_null_values_fixture(client, light_color_null_values_state) -> Node:
    """Mock a node with current color value item being null."""
    node = Node(client, copy.deepcopy(light_color_null_values_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="eaton_rf9640_dimmer")
def eaton_rf9640_dimmer_fixture(client, eaton_rf9640_dimmer_state) -> Node:
    """Mock a Eaton RF9640 (V4 compatible) dimmer node."""
    node = Node(client, copy.deepcopy(eaton_rf9640_dimmer_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_schlage_be469")
def lock_schlage_be469_fixture(client, lock_schlage_be469_state) -> Node:
    """Mock a schlage lock node."""
    node = Node(client, copy.deepcopy(lock_schlage_be469_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_august_pro")
def lock_august_asl03_fixture(client, lock_august_asl03_state) -> Node:
    """Mock a August Pro lock node."""
    node = Node(client, copy.deepcopy(lock_august_asl03_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct100_plus")
def climate_radio_thermostat_ct100_plus_fixture(
    client, climate_radio_thermostat_ct100_plus_state
) -> Node:
    """Mock a climate radio thermostat ct100 plus node."""
    node = Node(client, copy.deepcopy(climate_radio_thermostat_ct100_plus_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct100_plus_different_endpoints")
def climate_radio_thermostat_ct100_plus_different_endpoints_fixture(
    client, climate_radio_thermostat_ct100_plus_different_endpoints_state
) -> Node:
    """Mock climate radio thermostat ct100 plus node w/ values on diff endpoints."""
    node = Node(
        client,
        copy.deepcopy(climate_radio_thermostat_ct100_plus_different_endpoints_state),
    )
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000")
def climate_adc_t3000_fixture(client, climate_adc_t3000_state) -> Node:
    """Mock a climate ADC-T3000 node."""
    node = Node(client, copy.deepcopy(climate_adc_t3000_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_adc_t3000_missing_setpoint")
def climate_adc_t3000_missing_setpoint_fixture(client, climate_adc_t3000_state) -> Node:
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
def climate_adc_t3000_missing_mode_fixture(client, climate_adc_t3000_state) -> Node:
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
def climate_adc_t3000_missing_fan_mode_states_fixture(
    client, climate_adc_t3000_state
) -> Node:
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
def climate_danfoss_lc_13_fixture(client, climate_danfoss_lc_13_state) -> Node:
    """Mock a climate radio danfoss LC-13 node."""
    node = Node(client, copy.deepcopy(climate_danfoss_lc_13_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_eurotronic_spirit_z")
def climate_eurotronic_spirit_z_fixture(
    client, climate_eurotronic_spirit_z_state
) -> Node:
    """Mock a climate radio danfoss LC-13 node."""
    node = Node(client, climate_eurotronic_spirit_z_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm6")
def climate_heatit_z_trm6_fixture(client, climate_heatit_z_trm6_state) -> Node:
    """Mock a climate radio HEATIT Z-TRM6 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm6_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm3_no_value")
def climate_heatit_z_trm3_no_value_fixture(
    client, climate_heatit_z_trm3_no_value_state
) -> Node:
    """Mock a climate radio HEATIT Z-TRM3 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm3_no_value_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm3")
def climate_heatit_z_trm3_fixture(client, climate_heatit_z_trm3_state) -> Node:
    """Mock a climate radio HEATIT Z-TRM3 node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm3_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_heatit_z_trm2fx")
def climate_heatit_z_trm2fx_fixture(client, climate_heatit_z_trm2fx_state) -> Node:
    """Mock a climate radio HEATIT Z-TRM2fx node."""
    node = Node(client, copy.deepcopy(climate_heatit_z_trm2fx_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nortek_thermostat")
def nortek_thermostat_fixture(client, nortek_thermostat_state) -> Node:
    """Mock a nortek thermostat node."""
    node = Node(client, copy.deepcopy(nortek_thermostat_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="srt321_hrt4_zw")
def srt321_hrt4_zw_fixture(client, srt321_hrt4_zw_state) -> Node:
    """Mock a HRT4-ZW / SRT321 / SRT322 thermostat node."""
    node = Node(client, copy.deepcopy(srt321_hrt4_zw_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_radiator_thermostat")
def aeotec_radiator_thermostat_fixture(
    client, aeotec_radiator_thermostat_state
) -> Node:
    """Mock a Aeotec thermostat node."""
    node = Node(client, aeotec_radiator_thermostat_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nortek_thermostat_added_event")
def nortek_thermostat_added_event_fixture(client) -> Node:
    """Mock a Nortek thermostat node added event."""
    event_data = load_json_object_fixture("nortek_thermostat_added_event.json", DOMAIN)
    return Event("node added", event_data)


@pytest.fixture(name="nortek_thermostat_removed_event")
def nortek_thermostat_removed_event_fixture(client) -> Node:
    """Mock a Nortek thermostat node removed event."""
    event_data = load_json_object_fixture(
        "nortek_thermostat_removed_event.json", DOMAIN
    )
    return Event("node removed", event_data)


@pytest.fixture(name="integration")
async def integration_fixture(
    hass: HomeAssistant,
    client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the zwave_js integration."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    with patch("homeassistant.components.zwave_js.PLATFORMS", platforms):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client.async_send_command.reset_mock()

    return entry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS


@pytest.fixture(name="chain_actuator_zws12")
def window_cover_fixture(client, chain_actuator_zws12_state) -> Node:
    """Mock a window cover node."""
    node = Node(client, copy.deepcopy(chain_actuator_zws12_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fan_generic")
def fan_generic_fixture(client, fan_generic_state) -> Node:
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(fan_generic_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="hs_fc200")
def hs_fc200_fixture(client, hs_fc200_state) -> Node:
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(hs_fc200_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="leviton_zw4sf")
def leviton_zw4sf_fixture(client, leviton_zw4sf_state) -> Node:
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(leviton_zw4sf_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fan_honeywell_39358")
def fan_honeywell_39358_fixture(client, fan_honeywell_39358_state) -> Node:
    """Mock a fan node."""
    node = Node(client, copy.deepcopy(fan_honeywell_39358_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="null_name_check")
def null_name_check_fixture(client, null_name_check_state) -> Node:
    """Mock a node with no name."""
    node = Node(client, copy.deepcopy(null_name_check_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="gdc_zw062")
def motorized_barrier_cover_fixture(client, gdc_zw062_state) -> Node:
    """Mock a motorized barrier node."""
    node = Node(client, copy.deepcopy(gdc_zw062_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="iblinds_v2")
def iblinds_v2_cover_fixture(client, iblinds_v2_state) -> Node:
    """Mock an iBlinds v2.0 window cover node."""
    node = Node(client, copy.deepcopy(iblinds_v2_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="iblinds_v3")
def iblinds_v3_cover_fixture(client, iblinds_v3_state) -> Node:
    """Mock an iBlinds v3 window cover node."""
    node = Node(client, copy.deepcopy(iblinds_v3_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zvidar")
def zvidar_cover_fixture(client, zvidar_state) -> Node:
    """Mock a ZVIDAR window cover node."""
    node = Node(client, copy.deepcopy(zvidar_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="qubino_shutter")
def qubino_shutter_cover_fixture(client, qubino_shutter_state) -> Node:
    """Mock a Qubino flush shutter node."""
    node = Node(client, copy.deepcopy(qubino_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_nano_shutter")
def aeotec_nano_shutter_cover_fixture(client, aeotec_nano_shutter_state) -> Node:
    """Mock a Aeotec Nano Shutter node."""
    node = Node(client, copy.deepcopy(aeotec_nano_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fibaro_fgr222_shutter")
def fibaro_fgr222_shutter_cover_fixture(client, fibaro_fgr222_shutter_state) -> Node:
    """Mock a Fibaro FGR222 Shutter node."""
    node = Node(client, copy.deepcopy(fibaro_fgr222_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fibaro_fgr223_shutter")
def fibaro_fgr223_shutter_cover_fixture(client, fibaro_fgr223_shutter_state) -> Node:
    """Mock a Fibaro FGR223 Shutter node."""
    node = Node(client, copy.deepcopy(fibaro_fgr223_shutter_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="shelly_qnsh_001P10_shutter")
def shelly_qnsh_001P10_cover_shutter_fixture(
    client, shelly_europe_ltd_qnsh_001p10_state
) -> Node:
    """Mock a Shelly QNSH 001P10 Shutter node."""
    node = Node(client, copy.deepcopy(shelly_europe_ltd_qnsh_001p10_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="merten_507801")
def merten_507801_cover_fixture(client, merten_507801_state) -> Node:
    """Mock a Merten 507801 Shutter node."""
    node = Node(client, copy.deepcopy(merten_507801_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeon_smart_switch_6")
def aeon_smart_switch_6_fixture(client, aeon_smart_switch_6_state) -> Node:
    """Mock an AEON Labs (ZW096) Smart Switch 6 node."""
    node = Node(client, aeon_smart_switch_6_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ge_12730")
def ge_12730_fixture(client, ge_12730_state) -> Node:
    """Mock a GE 12730 fan controller node."""
    node = Node(client, copy.deepcopy(ge_12730_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="inovelli_lzw36")
def inovelli_lzw36_fixture(client, inovelli_lzw36_state) -> Node:
    """Mock a Inovelli LZW36 fan controller node."""
    node = Node(client, copy.deepcopy(inovelli_lzw36_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_id_lock_as_id150")
def lock_id_lock_as_id150_fixture(client, lock_id_lock_as_id150_state) -> Node:
    """Mock an id lock id-150 lock node."""
    node = Node(client, copy.deepcopy(lock_id_lock_as_id150_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_id_lock_as_id150_not_ready")
def node_not_ready_fixture(client, lock_id_lock_as_id150_state) -> Node:
    """Mock an id lock id-150 lock node that's not ready."""
    state = copy.deepcopy(lock_id_lock_as_id150_state)
    state["ready"] = False
    node = Node(client, state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="climate_radio_thermostat_ct101_multiple_temp_units")
def climate_radio_thermostat_ct101_multiple_temp_units_fixture(
    client, climate_radio_thermostat_ct101_multiple_temp_units_state
) -> Node:
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
) -> Node:
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
def vision_security_zl7432_fixture(client, vision_security_zl7432_state) -> Node:
    """Mock a vision security zl7432 node."""
    node = Node(client, copy.deepcopy(vision_security_zl7432_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zen_31")
def zen_31_fixture(client, zen_31_state) -> Node:
    """Mock a bulb 6 multi-color node."""
    node = Node(client, copy.deepcopy(zen_31_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="wallmote_central_scene")
def wallmote_central_scene_fixture(client, wallmote_central_scene_state) -> Node:
    """Mock a wallmote central scene node."""
    node = Node(client, copy.deepcopy(wallmote_central_scene_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="ge_in_wall_dimmer_switch")
def ge_in_wall_dimmer_switch_fixture(client, ge_in_wall_dimmer_switch_state) -> Node:
    """Mock a ge in-wall dimmer switch scene node."""
    node = Node(client, copy.deepcopy(ge_in_wall_dimmer_switch_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_zw164_siren")
def aeotec_zw164_siren_fixture(client, aeotec_zw164_siren_state) -> Node:
    """Mock a aeotec zw164 siren node."""
    node = Node(client, copy.deepcopy(aeotec_zw164_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_popp_electric_strike_lock_control")
def lock_popp_electric_strike_lock_control_fixture(
    client, lock_popp_electric_strike_lock_control_state
) -> Node:
    """Mock a popp electric strike lock control node."""
    node = Node(client, copy.deepcopy(lock_popp_electric_strike_lock_control_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fortrezz_ssa1_siren")
def fortrezz_ssa1_siren_fixture(client, fortrezz_ssa1_siren_state) -> Node:
    """Mock a fortrezz ssa1 siren node."""
    node = Node(client, copy.deepcopy(fortrezz_ssa1_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="fortrezz_ssa3_siren")
def fortrezz_ssa3_siren_fixture(client, fortrezz_ssa3_siren_state) -> Node:
    """Mock a fortrezz ssa3 siren node."""
    node = Node(client, copy.deepcopy(fortrezz_ssa3_siren_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="firmware_file")
def firmware_file_fixture() -> io.BytesIO:
    """Return mock firmware file stream."""
    return io.BytesIO(bytes(10))


@pytest.fixture(name="zp3111_not_ready")
def zp3111_not_ready_fixture(client, zp3111_not_ready_state) -> Node:
    """Mock a zp3111 4-in-1 sensor node in a not-ready state."""
    node = Node(client, copy.deepcopy(zp3111_not_ready_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zp3111")
def zp3111_fixture(client, zp3111_state) -> Node:
    """Mock a zp3111 4-in-1 sensor node."""
    node = Node(client, copy.deepcopy(zp3111_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="express_controls_ezmultipli")
def express_controls_ezmultipli_fixture(
    client, express_controls_ezmultipli_state
) -> Node:
    """Mock a Express Controls EZMultiPli node."""
    node = Node(client, copy.deepcopy(express_controls_ezmultipli_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="lock_home_connect_620")
def lock_home_connect_620_fixture(client, lock_home_connect_620_state) -> Node:
    """Mock a Home Connect 620 lock node."""
    node = Node(client, copy.deepcopy(lock_home_connect_620_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="switch_zooz_zen72")
def switch_zooz_zen72_fixture(client, switch_zooz_zen72_state) -> Node:
    """Mock a Zooz Zen72 switch node."""
    node = Node(client, copy.deepcopy(switch_zooz_zen72_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="indicator_test")
def indicator_test_fixture(client, indicator_test_state) -> Node:
    """Mock a indicator CC test node."""
    node = Node(client, copy.deepcopy(indicator_test_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="energy_production")
def energy_production_fixture(client, energy_production_state) -> Node:
    """Mock a mock node with Energy Production CC."""
    node = Node(client, copy.deepcopy(energy_production_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="nice_ibt4zwave")
def nice_ibt4zwave_fixture(client, nice_ibt4zwave_state) -> Node:
    """Mock a Nice IBT4ZWAVE cover node."""
    node = Node(client, copy.deepcopy(nice_ibt4zwave_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="logic_group_zdb5100")
def logic_group_zdb5100_fixture(client, logic_group_zdb5100_state) -> Node:
    """Mock a ZDB5100 light node."""
    node = Node(client, copy.deepcopy(logic_group_zdb5100_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="central_scene_node")
def central_scene_node_fixture(client, central_scene_node_state) -> Node:
    """Mock a node with the Central Scene CC."""
    node = Node(client, copy.deepcopy(central_scene_node_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="light_device_class_is_null")
def light_device_class_is_null_fixture(
    client, light_device_class_is_null_state
) -> Node:
    """Mock a node when device class is null."""
    node = Node(client, copy.deepcopy(light_device_class_is_null_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="basic_cc_sensor")
def basic_cc_sensor_fixture(client, basic_cc_sensor_state) -> Node:
    """Mock a node with a Basic CC."""
    node = Node(client, copy.deepcopy(basic_cc_sensor_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="window_covering_outbound_bottom")
def window_covering_outbound_bottom_fixture(
    client, window_covering_outbound_bottom_state
) -> Node:
    """Load node with Window Covering CC fixture data, with only the outbound bottom position supported."""
    node = Node(client, copy.deepcopy(window_covering_outbound_bottom_state))
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="siren_neo_coolcam")
def siren_neo_coolcam_fixture(
    client: MagicMock, siren_neo_coolcam_state: NodeDataType
) -> Node:
    """Load node for neo coolcam siren."""
    node = Node(client, siren_neo_coolcam_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="aeotec_smart_switch_7")
def aeotec_smart_switch_7_fixture(
    client: MagicMock, aeotec_smart_switch_7_state: NodeDataType
) -> Node:
    """Load node for Aeotec Smart Switch 7."""
    node = Node(client, aeotec_smart_switch_7_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


@pytest.fixture(name="zcombo_smoke_co_alarm")
def zcombo_smoke_co_alarm_fixture(
    client: MagicMock, zcombo_smoke_co_alarm_state: NodeDataType
) -> Node:
    """Load node for ZCombo-G Smoke/CO Alarm."""
    node = Node(client, zcombo_smoke_co_alarm_state)
    client.driver.controller.nodes[node.node_id] = node
    return node
