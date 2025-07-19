"""Tests for the Tuya component."""

from __future__ import annotations

from unittest.mock import patch

from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_MOCKS = {
    "cl_am43_corded_motor_zigbee_cover": [
        # https://github.com/home-assistant/core/issues/71242
        Platform.SELECT,
        Platform.COVER,
    ],
    "clkg_curtain_switch": [
        # https://github.com/home-assistant/core/issues/136055
        Platform.COVER,
        Platform.LIGHT,
    ],
    "co2bj_air_detector": [
        # https://github.com/home-assistant/core/issues/133173
        Platform.BINARY_SENSOR,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SIREN,
    ],
    "cs_arete_two_12l_dehumidifier_air_purifier": [
        Platform.BINARY_SENSOR,
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cs_emma_dehumidifier": [
        # https://github.com/home-assistant/core/issues/119865
        Platform.BINARY_SENSOR,
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cs_smart_dry_plus": [
        # https://github.com/home-assistant/core/issues/119865
        Platform.FAN,
        Platform.HUMIDIFIER,
    ],
    "cwjwq_smart_odor_eliminator": [
        # https://github.com/orgs/home-assistant/discussions/79
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cwwsq_cleverio_pf100": [
        # https://github.com/home-assistant/core/issues/144745
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    "cwysj_pixi_smart_drinking_fountain": [
        # https://github.com/home-assistant/core/pull/146599
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cz_dual_channel_metering": [
        # https://github.com/home-assistant/core/issues/147149
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "dj_smart_light_bulb": [
        # https://github.com/home-assistant/core/pull/126242
        Platform.LIGHT
    ],
    "dlq_earu_electric_eawcpt": [
        # https://github.com/home-assistant/core/issues/102769
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "dlq_metering_3pn_wifi": [
        # https://github.com/home-assistant/core/issues/143499
        Platform.SENSOR,
    ],
    "gyd_night_light": [
        # https://github.com/home-assistant/core/issues/133173
        Platform.LIGHT,
    ],
    "kg_smart_valve": [
        # https://github.com/home-assistant/core/issues/148347
        Platform.SWITCH,
    ],
    "kj_bladeless_tower_fan": [
        # https://github.com/orgs/home-assistant/discussions/61
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "ks_tower_fan": [
        # https://github.com/orgs/home-assistant/discussions/329
        Platform.FAN,
        Platform.LIGHT,
        Platform.SWITCH,
    ],
    "kt_serenelife_slpac905wuk_air_conditioner": [
        # https://github.com/home-assistant/core/pull/148646
        Platform.CLIMATE,
    ],
    "mal_alarm_host": [
        # Alarm Host support
        Platform.ALARM_CONTROL_PANEL,
        Platform.NUMBER,
        Platform.SWITCH,
    ],
    "mcs_door_sensor": [
        # https://github.com/home-assistant/core/issues/108301
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "qccdz_ac_charging_control": [
        # https://github.com/home-assistant/core/issues/136207
        Platform.SWITCH,
    ],
    "qxj_temp_humidity_external_probe": [
        # https://github.com/home-assistant/core/issues/136472
        Platform.SENSOR,
    ],
    "qxj_weather_station": [
        # https://github.com/orgs/home-assistant/discussions/318
        Platform.SENSOR,
    ],
    "rqbj_gas_sensor": [
        # https://github.com/orgs/home-assistant/discussions/100
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "sfkzq_valve_controller": [
        # https://github.com/home-assistant/core/issues/148116
        Platform.SWITCH,
    ],
    "tdq_4_443": [
        # https://github.com/home-assistant/core/issues/146845
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "wk_wifi_smart_gas_boiler_thermostat": [
        # https://github.com/orgs/home-assistant/discussions/243
        Platform.CLIMATE,
        Platform.NUMBER,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "wsdcg_temperature_humidity": [
        # https://github.com/home-assistant/core/issues/102769
        Platform.SENSOR,
    ],
    "wxkg_wireless_switch": [
        # https://github.com/home-assistant/core/issues/93975
        Platform.EVENT,
        Platform.SENSOR,
    ],
    "zndb_smart_meter": [
        # https://github.com/home-assistant/core/issues/138372
        Platform.SENSOR,
    ],
}


async def initialize_entry(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Initialize the Tuya component with a mock manager and config entry."""
    # Setup
    mock_manager.device_map = {
        mock_device.id: mock_device,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with patch(
        "homeassistant.components.tuya.ManagerCompat", return_value=mock_manager
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
