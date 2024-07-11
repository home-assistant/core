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
from syrupy import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .test_common import (
    DEFAULT_CONFIG,
    DEFAULT_SENSOR_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_deep_sleep_availability,
    help_test_deep_sleep_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
)

from tests.common import async_fire_mqtt_message, async_fire_time_changed
from tests.typing import MqttMockHAClient, MqttMockPahoClient

BAD_LIST_SENSOR_CONFIG_3 = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "ENERGY": {
            "ApparentPower": [7.84, 1.23, 2.34],
        },
    }
}

# This configuration has sensors which type we can't guess
DEFAULT_SENSOR_CONFIG_UNKNOWN = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "SENSOR1": {"Unknown": None},
        "SENSOR2": {"Unknown": "123"},
        "SENSOR3": {"Unknown": 123},
        "SENSOR4": {"Unknown": 123.0},
    }
}

# This configuration has some sensors where values are lists
# Home Assistant maps this to one sensor for each list item
LIST_SENSOR_CONFIG = {
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

# Same as LIST_SENSOR_CONFIG, but Total is also a list
LIST_SENSOR_CONFIG_2 = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "ENERGY": {
            "TotalStartTime": "2018-11-23T15:33:47",
            "Total": [0.000, 0.017],
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

# This configuration has some sensors where values are dicts
# Home Assistant maps this to one sensor for each dictionary item
DICT_SENSOR_CONFIG_1 = {
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

# Similar to LIST_SENSOR_CONFIG, but Total is a dict
DICT_SENSOR_CONFIG_2 = {
    "sn": {
        "Time": "2023-01-27T11:04:56",
        "ENERGY": {
            "Total": {
                "Phase1": 0.017,
                "Phase2": 0.017,
            },
            "TotalStartTime": "2018-11-23T15:33:47",
        },
    }
}

NUMBERED_SENSOR_CONFIG = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "ANALOG": {
            "Temperature1": 2.4,
            "Temperature2": 2.4,
            "Illuminance3": 2.4,
        },
        "TempUnit": "C",
    }
}

NUMBERED_SENSOR_CONFIG_2 = {
    "sn": {
        "Time": "2020-09-25T12:47:15",
        "ANALOG": {
            "CTEnergy1": {"Energy": 0.5, "Power": 2300, "Voltage": 230, "Current": 10},
        },
        "TempUnit": "C",
    }
}

TEMPERATURE_SENSOR_CONFIG = {
    "sn": {
        "Time": "2023-01-27T11:04:56",
        "DS18B20": {
            "Id": "01191ED79190",
            "Temperature": 2.4,
        },
        "TempUnit": "C",
    }
}


@pytest.mark.parametrize(
    ("sensor_config", "entity_ids", "messages"),
    [
        (
            DEFAULT_SENSOR_CONFIG,
            ["sensor.tasmota_dht11_temperature"],
            (
                '{"DHT11":{"Temperature":20.5}}',
                '{"StatusSNS":{"DHT11":{"Temperature":20.0}}}',
            ),
        ),
        (
            DICT_SENSOR_CONFIG_1,
            ["sensor.tasmota_tx23_speed_act", "sensor.tasmota_tx23_dir_card"],
            (
                '{"TX23":{"Speed":{"Act":"12.3"},"Dir": {"Card": "WSW"}}}',
                '{"StatusSNS":{"TX23":{"Speed":{"Act":"23.4"},"Dir": {"Card": "ESE"}}}}',
            ),
        ),
        (
            LIST_SENSOR_CONFIG,
            [
                "sensor.tasmota_energy_totaltariff_0",
                "sensor.tasmota_energy_totaltariff_1",
                "sensor.tasmota_energy_exporttariff_0",
                "sensor.tasmota_energy_exporttariff_1",
            ],
            (
                '{"ENERGY":{"ExportTariff":[5.6,7.8],"TotalTariff":[1.2,3.4]}}',
                '{"StatusSNS":{"ENERGY":{"ExportTariff":[1.2,3.4],"TotalTariff":[5.6,7.8]}}}',
            ),
        ),
        (
            TEMPERATURE_SENSOR_CONFIG,
            ["sensor.tasmota_ds18b20_temperature", "sensor.tasmota_ds18b20_id"],
            (
                '{"DS18B20":{"Id": "01191ED79190","Temperature": 12.3}}',
                '{"StatusSNS":{"DS18B20":{"Id": "meep","Temperature": 23.4}}}',
            ),
        ),
        # Test simple Total sensor
        (
            LIST_SENSOR_CONFIG,
            ["sensor.tasmota_energy_total"],
            (
                '{"ENERGY":{"Total":1.2,"TotalStartTime":"2018-11-23T15:33:47"}}',
                '{"StatusSNS":{"ENERGY":{"Total":5.6,"TotalStartTime":"2018-11-23T16:33:47"}}}',
            ),
        ),
        # Test list Total sensors
        (
            LIST_SENSOR_CONFIG_2,
            ["sensor.tasmota_energy_total_0", "sensor.tasmota_energy_total_1"],
            (
                '{"ENERGY":{"Total":[1.2, 3.4],"TotalStartTime":"2018-11-23T15:33:47"}}',
                '{"StatusSNS":{"ENERGY":{"Total":[5.6, 7.8],"TotalStartTime":"2018-11-23T16:33:47"}}}',
            ),
        ),
        # Test dict Total sensors
        (
            DICT_SENSOR_CONFIG_2,
            [
                "sensor.tasmota_energy_total_phase1",
                "sensor.tasmota_energy_total_phase2",
            ],
            (
                '{"ENERGY":{"Total":{"Phase1":1.2, "Phase2":3.4},"TotalStartTime":"2018-11-23T15:33:47"}}',
                '{"StatusSNS":{"ENERGY":{"Total":{"Phase1":5.6, "Phase2":7.8},"TotalStartTime":"2018-11-23T15:33:47"}}}',
            ),
        ),
        (
            NUMBERED_SENSOR_CONFIG,
            [
                "sensor.tasmota_analog_temperature1",
                "sensor.tasmota_analog_temperature2",
                "sensor.tasmota_analog_illuminance3",
            ],
            (
                (
                    '{"ANALOG":{"Temperature1":1.2,"Temperature2":3.4,'
                    '"Illuminance3": 5.6}}'
                ),
                (
                    '{"StatusSNS":{"ANALOG":{"Temperature1": 7.8,"Temperature2": 9.0,'
                    '"Illuminance3":1.2}}}'
                ),
            ),
        ),
        (
            NUMBERED_SENSOR_CONFIG_2,
            [
                "sensor.tasmota_analog_ctenergy1_energy",
                "sensor.tasmota_analog_ctenergy1_power",
                "sensor.tasmota_analog_ctenergy1_voltage",
                "sensor.tasmota_analog_ctenergy1_current",
            ],
            (
                (
                    '{"ANALOG":{"CTEnergy1":'
                    '{"Energy":0.5,"Power":2300,"Voltage":230,"Current":10}}}'
                ),
                (
                    '{"StatusSNS":{"ANALOG":{"CTEnergy1":'
                    '{"Energy":1.0,"Power":1150,"Voltage":230,"Current":5}}}}'
                ),
            ),
        ),
        # Test we automatically set state class to measurement on unknown numerical sensors
        (
            DEFAULT_SENSOR_CONFIG_UNKNOWN,
            [
                "sensor.tasmota_sensor1_unknown",
                "sensor.tasmota_sensor2_unknown",
                "sensor.tasmota_sensor3_unknown",
                "sensor.tasmota_sensor4_unknown",
            ],
            (
                '{"SENSOR1":{"Unknown":20.5},"SENSOR2":{"Unknown":20.5},"SENSOR3":{"Unknown":20.5},"SENSOR4":{"Unknown":20.5}}',
                '{"StatusSNS":{"SENSOR1":{"Unknown":20},"SENSOR2":{"Unknown":20},"SENSOR3":{"Unknown":20},"SENSOR4":{"Unknown":20}}}',
            ),
        ),
    ],
)
async def test_controlling_state_via_mqtt(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    snapshot: SnapshotAssertion,
    setup_tasmota,
    sensor_config,
    entity_ids,
    messages,
) -> None:
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(sensor_config)
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

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state.state == "unavailable"
        assert not state.attributes.get(ATTR_ASSUMED_STATE)
        assert state == snapshot

        entry = entity_registry.async_get(entity_id)
        assert entry.disabled is False
        assert entry.disabled_by is None
        assert entry.entity_category is None
        assert entry == snapshot

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test periodic state update
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/SENSOR", messages[0])
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state == snapshot

    # Test polled state update
    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/STATUS10", messages[1])
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state == snapshot


@pytest.mark.parametrize(
    ("sensor_config", "entity_ids", "states"),
    [
        (
            # The AS33935 energy sensor is not reporting energy in W
            {"sn": {"Time": "2020-09-25T12:47:15", "AS3935": {"Energy": None}}},
            ["sensor.tasmota_as3935_energy"],
            {
                "sensor.tasmota_as3935_energy": {
                    "device_class": None,
                    "state_class": None,
                    "unit_of_measurement": None,
                },
            },
        ),
        (
            # The AS33935 energy sensor is not reporting energy in W
            {"sn": {"Time": "2020-09-25T12:47:15", "LD2410": {"Energy": None}}},
            ["sensor.tasmota_ld2410_energy"],
            {
                "sensor.tasmota_ld2410_energy": {
                    "device_class": None,
                    "state_class": None,
                    "unit_of_measurement": None,
                },
            },
        ),
        (
            # Check other energy sensors work
            {"sn": {"Time": "2020-09-25T12:47:15", "Other": {"Energy": None}}},
            ["sensor.tasmota_other_energy"],
            {
                "sensor.tasmota_other_energy": {
                    "device_class": "energy",
                    "state_class": "total",
                    "unit_of_measurement": "kWh",
                },
            },
        ),
    ],
)
async def test_quantity_override(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
    sensor_config,
    entity_ids,
    states,
) -> None:
    """Test quantity override for certain sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(sensor_config)
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

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state.state == "unavailable"
        expected_state = states[entity_id]
        for attribute, expected in expected_state.get("attributes", {}).items():
            assert state.attributes.get(attribute) == expected

        entry = entity_registry.async_get(entity_id)
        assert entry.disabled is False
        assert entry.disabled_by is None
        assert entry.entity_category is None


async def test_bad_indexed_sensor_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test state update via MQTT where sensor is not matching configuration."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(BAD_LIST_SENSOR_CONFIG_3)
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

    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test periodic state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"ENERGY":{"ApparentPower":[1.2,3.4,5.6]}}'
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "1.2"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "3.4"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"

    # Test periodic state update with too few values
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"ENERGY":{"ApparentPower":[7.8,9.0]}}'
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "7.8"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "9.0"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/SENSOR", '{"ENERGY":{"ApparentPower":2.3}}'
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "2.3"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "9.0"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"ENERGY":{"ApparentPower":[1.2,3.4,5.6]}}}',
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "1.2"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "3.4"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"

    # Test polled state update with too few values
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"ENERGY":{"ApparentPower":[7.8,9.0]}}}',
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "7.8"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "9.0"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"

    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS10",
        '{"StatusSNS":{"ENERGY":{"ApparentPower":2.3}}}',
    )
    state = hass.states.get("sensor.tasmota_energy_apparentpower_0")
    assert state.state == "2.3"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_1")
    assert state.state == "9.0"
    state = hass.states.get("sensor.tasmota_energy_apparentpower_2")
    assert state.state == "5.6"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_status_sensor_state_via_mqtt(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test state update via MQTT."""
    # Pre-enable the status sensor
    entity_registry.async_get_or_create(
        Platform.SENSOR,
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
    await hass.async_block_till_done()
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

    # Test force update flag
    entity = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.tasmota_status"
    )
    assert not entity.force_update


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_battery_sensor_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["bat"] = 1  # BatteryPercentage feature enabled
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tasmota_battery_level")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_battery_level")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test pushed state update
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"BatteryPercentage":55}'
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_battery_level")
    assert state.state == "55"
    assert state.attributes == {
        "device_class": "battery",
        "friendly_name": "Tasmota Battery Level",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }

    # Test polled state update
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS11",
        '{"StatusSTS":{"BatteryPercentage":50}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_battery_level")
    assert state.state == "50"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_single_shot_status_sensor_state_via_mqtt(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test state update via MQTT."""
    # Pre-enable the status sensor
    entity_registry.async_get_or_create(
        Platform.SENSOR,
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
    await hass.async_block_till_done()
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
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test state update via MQTT."""

    # Pre-enable the status sensor
    entity_registry.async_get_or_create(
        Platform.SENSOR,
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
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Test polled state update
    utc_now = datetime.datetime(2020, 11, 11, 8, 0, 0, tzinfo=dt_util.UTC)
    hatasmota.status_sensor.datetime.now.return_value = utc_now
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/stat/STATUS11",
        '{"StatusSTS":{"UptimeSec":"3600"}}',
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_status")
    assert state.state == "2020-11-11T07:00:00+00:00"


async def test_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
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
    assert state.attributes.get("device_class") == "carbon_dioxide"
    assert state.attributes.get("friendly_name") == "Tasmota Beer CarbonDioxide"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "ppm"


async def test_nested_sensor_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test correct attributes for sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DICT_SENSOR_CONFIG_1)
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
    assert state.attributes.get("unit_of_measurement") is None


async def test_indexed_sensor_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
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
    assert state.attributes.get("device_class") == "carbon_dioxide"
    assert state.attributes.get("friendly_name") == "Tasmota Dummy2 CarbonDioxide 1"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "ppm"


@pytest.mark.parametrize("status_sensor_disabled", [False])
@pytest.mark.parametrize(
    ("sensor_name", "disabled", "disabled_by"),
    [
        ("tasmota_firmware_version", True, er.RegistryEntryDisabler.INTEGRATION),
        ("tasmota_ip", True, er.RegistryEntryDisabler.INTEGRATION),
        ("tasmota_last_restart_time", False, None),
        ("tasmota_mqtt_connect_count", False, None),
        ("tasmota_rssi", True, er.RegistryEntryDisabler.INTEGRATION),
        ("tasmota_signal", True, er.RegistryEntryDisabler.INTEGRATION),
        ("tasmota_ssid", False, None),
        ("tasmota_wifi_connect_count", False, None),
    ],
)
async def test_diagnostic_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
    sensor_name,
    disabled,
    disabled_by,
) -> None:
    """Test properties of diagnostic sensors."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{sensor_name}")
    assert bool(state) != disabled
    entry = entity_registry.async_get(f"sensor.{sensor_name}")
    assert entry.disabled == disabled
    assert entry.disabled_by is disabled_by
    assert entry.entity_category == "diagnostic"


@pytest.mark.parametrize("status_sensor_disabled", [False])
async def test_enable_status_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test enabling status sensor."""
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
    entry = entity_registry.async_get("sensor.tasmota_signal")
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable the signal level status sensor
    updated_entry = entity_registry.async_update_entity(
        "sensor.tasmota_signal", disabled_by=None
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow()
        + timedelta(seconds=config_entries.RELOAD_AFTER_UPDATE_DELAY + 1),
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
    await hass.async_block_till_done()
    state = hass.states.get("sensor.tasmota_signal")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability_when_connection_lost(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_deep_sleep_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_deep_sleep_availability_when_connection_lost(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability(
        hass,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_deep_sleep_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_deep_sleep_availability(
        hass,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_availability_discovery_update(
        hass,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_availability_poll_state(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    poll_topic = "tasmota_49A3BC/cmnd/STATUS"
    await help_test_availability_poll_state(
        hass,
        mqtt_client_mock,
        mqtt_mock,
        Platform.SENSOR,
        config,
        poll_topic,
        "10",
        sensor_config,
    )


async def test_discovery_removal_sensor(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removal of discovered sensor."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config1 = copy.deepcopy(DEFAULT_SENSOR_CONFIG)

    await help_test_discovery_removal(
        hass,
        mqtt_mock,
        caplog,
        Platform.SENSOR,
        config,
        config,
        sensor_config1,
        {},
        "tasmota_dht11_temperature",
        "Tasmota DHT11 Temperature",
    )


async def test_discovery_update_unchanged_sensor(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
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
            Platform.SENSOR,
            config,
            discovery_update,
            sensor_config,
            "tasmota_dht11_temperature",
            "Tasmota DHT11 Temperature",
        )


async def test_discovery_device_remove(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    unique_id = f"{DEFAULT_CONFIG['mac']}_sensor_sensor_DHT11_Temperature"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, Platform.SENSOR, unique_id, config, sensor_config
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
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
        Platform.SENSOR,
        config,
        topics,
        sensor_config,
        "tasmota_dht11_temperature",
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    sensor_config = copy.deepcopy(DEFAULT_SENSOR_CONFIG)
    await help_test_entity_id_update_discovery_update(
        hass,
        mqtt_mock,
        Platform.SENSOR,
        config,
        sensor_config,
        "tasmota_dht11_temperature",
    )
