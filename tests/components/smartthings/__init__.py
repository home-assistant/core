"""Tests for the SmartThings integration."""

from functools import cache
from typing import Any
from unittest.mock import AsyncMock

from pysmartthings import (
    Attribute,
    Capability,
    DeviceEvent,
    DeviceHealthEvent,
    DeviceResponse,
    DeviceStatus,
)
from pysmartthings.models import HealthStatus
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings.const import DOMAIN, MAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture

DEVICE_FIXTURES = [
    "aq_sensor_3_ikea",
    "aqara_g350",
    "aeotec_ms6",
    "da_ac_air_000001",
    "da_ac_air_01011",
    "da_ac_airsensor_01001",
    "da_ac_rac_000001",
    "da_ac_rac_000003",
    "da_ac_rac_100001",
    "da_ac_rac_01001",
    "da_ac_cac_01001",
    "multipurpose_sensor",
    "contact_sensor",
    "base_electric_meter",
    "smart_plug",
    "vd_stv_2017_k",
    "c2c_arlo_pro_3_switch",
    "yale_push_button_deadbolt_lock",
    "ge_in_wall_smart_dimmer",
    "centralite",
    "da_ref_normal_100001",
    "da_ref_normal_000001",
    "da_ref_normal_01011",
    "da_ref_normal_01011_onedoor",
    "da_ref_normal_01001",
    "vd_network_audio_002s",
    "vd_network_audio_003s",
    "vd_sensor_light_2023",
    "iphone",
    "ikea_leak_battery",
    "ikea_motion_illuminance_battery",
    "ikea_plug_powermeter",
    "aeotec_smart_home_hub",
    "meross_plug",
    "da_sac_ehs_000001_sub",
    "da_sac_ehs_000001_sub_1",
    "da_sac_ehs_000002_sub",
    "da_ac_ehs_01001",
    "da_wm_dw_000001",
    "da_wm_wd_01011",
    "da_wm_wd_000001",
    "da_wm_wd_000001_1",
    "da_wm_wm_01011",
    "da_wm_wm_100001",
    "da_wm_wm_100002",
    "da_wm_wm_000001",
    "da_wm_wm_000001_1",
    "da_wm_mf_01001",
    "da_wm_sc_000001",
    "da_wm_dw_01011",
    "da_rvc_normal_000001",
    "da_rvc_map_01011",
    "da_vc_stick_01001",
    "da_ks_microwave_0101x",
    "da_ks_cooktop_000001",
    "da_ks_cooktop_31001",
    "da_ks_range_0101x",
    "da_ks_oven_01061",
    "da_ks_oven_0107x",
    "da_ks_walloven_0107x",
    "da_ks_hood_01001",
    "hue_color_temperature_bulb",
    "hue_rgbw_color_bulb",
    "c2c_shade",
    "sonos_player",
    "aeotec_home_energy_meter_gen5",
    "virtual_water_sensor",
    "virtual_thermostat",
    "virtual_valve",
    "sensibo_airconditioner_1",
    "ecobee_sensor",
    "ecobee_thermostat",
    "ecobee_thermostat_offline",
    "sensi_thermostat",
    "siemens_washer",
    "fake_fan",
    "generic_fan_3_speed",
    "heatit_ztrm3_thermostat",
    "heatit_zpushwall",
    "generic_ef00_v1",
    "gas_detector",
    "bosch_radiator_thermostat_ii",
    "im_speaker_ai_0001",
    "im_smarttag2_ble_uwb",
    "abl_light_b_001",
    "tplink_p110",
    "ikea_kadrilj",
    "aux_ac",
    "hw_q80r_soundbar",
    "gas_meter",
    "lumi",
    "tesla_powerwall",
]


def get_device_status(device_name: str) -> DeviceStatus:
    """Load a DeviceStatus object from a fixture for the given device name."""
    return DeviceStatus.from_json(
        load_fixture(f"device_status/{device_name}.json", DOMAIN)
    )


def get_device_response(device_name: str) -> DeviceResponse:
    """Load a DeviceResponse object from a fixture for the given device name."""
    return DeviceResponse.from_json(load_fixture(f"devices/{device_name}.json", DOMAIN))


@cache
def get_fixture_name(device_id: str) -> str:
    """Get the fixture name for a given device ID."""
    for fixture_name in DEVICE_FIXTURES:
        for device in get_device_response(fixture_name).items:
            if device.device_id == device_id:
                return fixture_name

    raise KeyError(f"Fixture for device_id {device_id} not found")


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def snapshot_smartthings_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot SmartThings entities."""
    entities = hass.states.async_all(platform)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        prefix = ""
        if platform != Platform.SCENE:
            # SCENE unique id is not based on device fixture
            device_id = entity_entry.unique_id[:36]
            prefix = f"{get_fixture_name(device_id)}]["
        assert entity_entry == snapshot(name=f"{prefix}{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{prefix}{entity_entry.entity_id}-state")


def set_attribute_value(
    mock: AsyncMock,
    capability: Capability,
    attribute: Attribute,
    value: Any,
    component: str = MAIN,
) -> None:
    """Set the value of an attribute."""
    mock.get_device_status.return_value[component][capability][attribute].value = value


async def trigger_update(
    hass: HomeAssistant,
    mock: AsyncMock,
    device_id: str,
    capability: Capability,
    attribute: Attribute,
    value: str | float | dict[str, Any] | list[Any] | None,
    data: dict[str, Any] | None = None,
    component: str = MAIN,
) -> None:
    """Trigger an update."""
    event = DeviceEvent(
        "abc",
        "abc",
        "abc",
        device_id,
        component,
        capability,
        attribute,
        value,
        data,
    )
    for call in mock.add_unspecified_device_event_listener.call_args_list:
        call[0][0](event)
    for call in mock.add_device_event_listener.call_args_list:
        if call[0][0] == device_id:
            call[0][3](event)
    for call in mock.add_device_capability_event_listener.call_args_list:
        if call[0][0] == device_id and call[0][2] == capability:
            call[0][3](event)
    await hass.async_block_till_done()


async def trigger_health_update(
    hass: HomeAssistant, mock: AsyncMock, device_id: str, status: HealthStatus
) -> None:
    """Trigger a health update."""
    event = DeviceHealthEvent("abc", "abc", status)
    for call in mock.add_device_availability_event_listener.call_args_list:
        if call[0][0] == device_id:
            call[0][1](event)
    await hass.async_block_till_done()
