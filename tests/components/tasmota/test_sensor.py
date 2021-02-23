"""The tests for the Tasmota sensor platform."""
import copy
import datetime
from datetime import timedelta
import json
from unittest.mock import Mock, patch

import hatasmota
from hatasmota.utils import (
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
)
import pytest

from homeassistant import config_entries
from homeassistant.components import sensor
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNKNOWN
from homeassistant.util import dt

from .test_common import (
    DEFAULT_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
)

from tests.common import async_fire_mqtt_message, async_fire_time_changed

DEFAULT_SENSOR_CONFIG = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "DHT11": {"Temperature": None},
        "TempUnit": "C",
    }
}

INDEXED_SENSOR_CONFIG = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "ENERGY": {
            "TotalStartTime": "2018-11-23T15:33:47",
            "Total": 0.017,
            "TotalTariff": [0.000, 0.017],
            "Yesterday": 0.000,
            "Today": 0.002,
            "ExportActive": 0.000,
            "ExportTariff": [0.000, 0.000],
            "Period": 0.00,
            "Power": 0.00,
            "ApparentPower": 7.84,
            "ReactivePower": -7.21,
            "Factor": 0.39,
            "Frequency": 50.0,
            "Voltage": 234.31,
            "Current": 0.039,
            "ImportActive": 12.580,
            "ImportReactive": 0.002,
            "ExportReactive": 39.131,
            "PhaseAngle": 290.45,
        },
    }
}


NESTED_SENSOR_CONFIG = {
    "sn": {
        "Time": "2020-03-03T00:00:00+00:00",
        "TX23": {
            "Speed": {"Act": 14.8, "Avg": 8.5, "Min": 12.2, "Max": 14.8},
            "Dir": {
                "Card": "WSW",
                "Deg": 247.5,
                "Avg": 266.1,
                "AvgCard": "W",
                "Range": 0,
            },
        },
        "SpeedUnit": "km/h",
    }
}


async def test_controlling_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_dht11_temperature")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_dht11_temperature")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test periodic state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"DHT11":{"Temperature":20.5}}'
    )
    state = hass.states.get("sensor.tasmota_dht11_temperature")
    assert state.state == "20.5"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"DHT11":{"Temperature":20.0}}}',
    )
    state = hass.states.get("sensor.tasmota_dht11_temperature")
    assert state.state == "20.0"


async def test_nested_sensor_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(NESTED_SENSOR_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_tx23_speed_act")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_tx23_speed_act")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test periodic state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"TX23":{"Speed":{"Act":"12.3"}}}'
    )
    state = hass.states.get("sensor.tasmota_tx23_speed_act")
    assert state.state == "12.3"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"TX23":{"Speed":{"Act":"23.4"}}}}',
    )
    state = hass.states.get("sensor.tasmota_tx23_speed_act")
    assert state.state == "23.4"


async def test_indexed_sensor_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(INDEXED_SENSOR_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_energy_totaltariff_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_energy_totaltariff_1")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test periodic state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"ENERGY":{"TotalTariff":[1.2,3.4]}}'
    )
    state = hass.states.get("sensor.tasmota_energy_totaltariff_1")
    assert state.state == "3.4"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"ENERGY":{"TotalTariff":[5.6,7.8]}}}',
    )
    state = hass.states.get("sensor.tasmota_energy_totaltariff_1")
    assert state.state == "7.8"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_status_sensor_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    # Pre-enable the status sensor
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        "tasmota",
        "00000049A3BC_status_sensor_status_sensor_status_signal",
        suggested_object_id="tasmota_status",
        disabled_by=None,
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test pushed state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"Wifi":{"Signal":20.5}}'
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "20.5"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS11",
        '{"StatusSTS":{"Wifi":{"Signal":20.0}}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "20.0"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_single_shot_status_sensor_state_via_mqtt(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    # Pre-enable the status sensor
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        "tasmota",
        "00000049A3BC_status_sensor_status_sensor_status_restart_reason",
        suggested_object_id="tasmota_status",
        disabled_by=None,
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS1",
        '{"StatusPRM":{"RestartReason":"Some reason"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "Some reason"

    # Test polled state update is ignored
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS1",
        '{"StatusPRM":{"RestartReason":"Another reason"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "Some reason"

    # Device signals online again
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "Some reason"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS1",
        '{"StatusPRM":{"RestartReason":"Another reason"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "Another reason"

    # Test polled state update is ignored
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS1",
        '{"StatusPRM":{"RestartReason":"Third reason"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "Another reason"


@pytest.mark.parametrize("status_sensor_disabled", [False])
@patch.object(hatasmota.status_sensor, "datetime", Mock(wraps=datetime.datetime))
async def test_restart_time_status_sensor_state_via_mqtt(
    hass, mqtt_mock, setup_tasmota
):
    """Test state update via MQTT."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    # Pre-enable the status sensor
    entity_reg.async_get_or_create(
        sensor.DOMAIN,
        "tasmota",
        "00000049A3BC_status_sensor_status_sensor_last_restart_time",
        suggested_object_id="tasmota_status",
        disabled_by=None,
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test polled state update
    utc_now = datetime.datetime(2020, 11, 11, 8, 0, 0, tzinfo=dt.UTC)
    hatasmota.status_sensor.datetime.now.return_value = utc_now
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS11",
        '{"StatusSTS":{"UptimeSec":"3600"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "2020-11-11T07:00:00+00:00"


async def test_attributes(hass, mqtt_mock, setup_tasmota):
    """Test correct attributes for sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = {
        "sn": {
            "DHT11": {"Temperature": None},
            "Beer": {"CarbonDioxide": None},
            "TempUnit": "C",
        }
    }
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_dht11_temperature")
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("friendly_name") == "Tasmota DHT11 Temperature"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "°C"

    state = hass.states.get("sensor.tasmota_beer_CarbonDioxide")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("friendly_name") == "Tasmota Beer CarbonDioxide"
    assert state.attributes.get("icon") == "mdi:molecule-co2"
    assert state.attributes.get("unit_of_measurement") == "ppm"


async def test_nested_sensor_attributes(hass, mqtt_mock, setup_tasmota):
    """Test correct attributes for sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(NESTED_SENSOR_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_tx23_speed_act")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("friendly_name") == "Tasmota TX23 Speed Act"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "km/h"

    state = hass.states.get("sensor.tasmota_tx23_dir_avg")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("friendly_name") == "Tasmota TX23 Dir Avg"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == " "


async def test_indexed_sensor_attributes(hass, mqtt_mock, setup_tasmota):
    """Test correct attributes for sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = {
        "sn": {
            "Dummy1": {"Temperature": [None, None]},
            "Dummy2": {"CarbonDioxide": [None, None]},
            "TempUnit": "C",
        }
    }
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/sensors",
        json.dumps(sensor_config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_dummy1_temperature_0")
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("friendly_name") == "Tasmota Dummy1 Temperature 0"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "°C"

    state = hass.states.get("sensor.tasmota_dummy2_carbondioxide_1")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("friendly_name") == "Tasmota Dummy2 CarbonDioxide 1"
    assert state.attributes.get("icon") == "mdi:molecule-co2"
    assert state.attributes.get("unit_of_measurement") == "ppm"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_enable_status_sensor(hass, mqtt_mock, setup_tasmota):
    """Test enabling status sensor."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_signal")
    assert state is None
    entry = entity_reg.async_get("sensor.tasmota_signal")
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Enable the status sensor
    updated_entry = entity_reg.async_update_entity(
        "sensor.tasmota_signal", disabled_by=None
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=config_entries.RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Fake re-send of retained discovery message
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_signal")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("sensor.tasmota_signal")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_availability_when_connection_lost(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability_when_connection_lost(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability(hass, mqtt_mock, setup_tasmota):
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability(
        hass,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability_discovery_update(
        hass,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability_poll_state(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    poll_topic = "tasmota_49A3BC/cmnd/STATUS"
    await help_test_availability_poll_state(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        poll_topic,
        "10",
        sensor_config,
    )


async def test_discovery_removal_sensor(hass, mqtt_mock, caplog, setup_tasmota):
    """Test removal of discovered sensor."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config1 = copy.deepcopy(DEFAULT_SENSOR_CONFIG)

    await help_test_discovery_removal(
        hass,
        mqtt_mock,
        caplog,
        sensor.DOMAIN,
        config,
        config,
        sensor_config1,
        {},
        "tasmota_dht11_temperature",
        "Tasmota DHT11 Temperature",
    )


async def test_discovery_update_unchanged_sensor(
    hass, mqtt_mock, caplog, setup_tasmota
):
    """Test update of discovered sensor."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    with patch(
        "homeassistant.components.tasmota.sensor.TasmotaSensor.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock,
            caplog,
            sensor.DOMAIN,
            config,
            discovery_update,
            sensor_config,
            "tasmota_dht11_temperature",
            "Tasmota DHT11 Temperature",
        )


async def test_discovery_device_remove(hass, mqtt_mock, setup_tasmota):
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    unique_id = f"{DEFAULT_CONFIG['mac']}_sensor_sensor_DHT11_Temperature"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, sensor.DOMAIN, unique_id, config, sensor_config
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock, setup_tasmota):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    topics = [
        get_topic_tele_sensor(config),
        get_topic_stat_status(config, 10),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        topics,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_entity_id_update_discovery_update(
        hass,
        mqtt_mock,
        sensor.DOMAIN,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )
