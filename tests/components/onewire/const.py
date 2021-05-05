"""Constants for 1-Wire integration."""

from pi1wire import InvalidCRCException, UnsupportResponseException
from pyownet.protocol import Error as ProtocolError

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.onewire.const import DOMAIN, PRESSURE_CBAR
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_MBAR,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    VOLT,
)

MOCK_OWPROXY_DEVICES = {
    "00.111111111111": {
        "inject_reads": [
            b"",  # read device type
        ],
        SENSOR_DOMAIN: [],
    },
    "05.111111111111": {
        "inject_reads": [
            b"DS2405",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "05.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2405",
            "name": "05.111111111111",
        },
        SWITCH_DOMAIN: [
            {
                "entity_id": "switch.05_111111111111_pio",
                "unique_id": "/05.111111111111/PIO",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
    },
    "10.111111111111": {
        "inject_reads": [
            b"DS18S20",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "10.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS18S20",
            "name": "10.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.my_ds18b20_temperature",
                "unique_id": "/10.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "12.111111111111": {
        "inject_reads": [
            b"DS2406",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "12.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2406",
            "name": "12.111111111111",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                "entity_id": "binary_sensor.12_111111111111_sensed_a",
                "unique_id": "/12.111111111111/sensed.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.12_111111111111_sensed_b",
                "unique_id": "/12.111111111111/sensed.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.12_111111111111_temperature",
                "unique_id": "/12.111111111111/TAI8570/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
                "disabled": True,
            },
            {
                "entity_id": "sensor.12_111111111111_pressure",
                "unique_id": "/12.111111111111/TAI8570/pressure",
                "injected_value": b"  1025.123",
                "result": "1025.1",
                "unit": PRESSURE_MBAR,
                "class": DEVICE_CLASS_PRESSURE,
                "disabled": True,
            },
        ],
        SWITCH_DOMAIN: [
            {
                "entity_id": "switch.12_111111111111_pio_a",
                "unique_id": "/12.111111111111/PIO.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_pio_b",
                "unique_id": "/12.111111111111/PIO.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_latch_a",
                "unique_id": "/12.111111111111/latch.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_latch_b",
                "unique_id": "/12.111111111111/latch.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
    },
    "1D.111111111111": {
        "inject_reads": [
            b"DS2423",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "1D.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2423",
            "name": "1D.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.1d_111111111111_counter_a",
                "unique_id": "/1D.111111111111/counter.A",
                "injected_value": b"    251123",
                "result": "251123",
                "unit": "count",
                "class": None,
            },
            {
                "entity_id": "sensor.1d_111111111111_counter_b",
                "unique_id": "/1D.111111111111/counter.B",
                "injected_value": b"    248125",
                "result": "248125",
                "unit": "count",
                "class": None,
            },
        ],
    },
    "1F.111111111111": {
        "inject_reads": [
            b"DS2409",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "1F.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2409",
            "name": "1F.111111111111",
        },
        "branches": {
            "aux": {},
            "main": {
                "1D.111111111111": {
                    "inject_reads": [
                        b"DS2423",  # read device type
                    ],
                    "device_info": {
                        "identifiers": {(DOMAIN, "1D.111111111111")},
                        "manufacturer": "Maxim Integrated",
                        "model": "DS2423",
                        "name": "1D.111111111111",
                    },
                    SENSOR_DOMAIN: [
                        {
                            "entity_id": "sensor.1d_111111111111_counter_a",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.A",
                            "unique_id": "/1D.111111111111/counter.A",
                            "injected_value": b"    251123",
                            "result": "251123",
                            "unit": "count",
                            "class": None,
                        },
                        {
                            "entity_id": "sensor.1d_111111111111_counter_b",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.B",
                            "unique_id": "/1D.111111111111/counter.B",
                            "injected_value": b"    248125",
                            "result": "248125",
                            "unit": "count",
                            "class": None,
                        },
                    ],
                },
            },
        },
    },
    "22.111111111111": {
        "inject_reads": [
            b"DS1822",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "22.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS1822",
            "name": "22.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.22_111111111111_temperature",
                "unique_id": "/22.111111111111/temperature",
                "injected_value": ProtocolError,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "26.111111111111": {
        "inject_reads": [
            b"DS2438",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "26.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2438",
            "name": "26.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.26_111111111111_temperature",
                "unique_id": "/26.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity",
                "unique_id": "/26.111111111111/humidity",
                "injected_value": b"    72.7563",
                "result": "72.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih3600",
                "unique_id": "/26.111111111111/HIH3600/humidity",
                "injected_value": b"    73.7563",
                "result": "73.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih4000",
                "unique_id": "/26.111111111111/HIH4000/humidity",
                "injected_value": b"    74.7563",
                "result": "74.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih5030",
                "unique_id": "/26.111111111111/HIH5030/humidity",
                "injected_value": b"    75.7563",
                "result": "75.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_htm1735",
                "unique_id": "/26.111111111111/HTM1735/humidity",
                "injected_value": ProtocolError,
                "result": "unknown",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_pressure",
                "unique_id": "/26.111111111111/B1-R1-A/pressure",
                "injected_value": b"    969.265",
                "result": "969.3",
                "unit": PRESSURE_MBAR,
                "class": DEVICE_CLASS_PRESSURE,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_illuminance",
                "unique_id": "/26.111111111111/S3-R1-A/illuminance",
                "injected_value": b"    65.8839",
                "result": "65.9",
                "unit": LIGHT_LUX,
                "class": DEVICE_CLASS_ILLUMINANCE,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_voltage_vad",
                "unique_id": "/26.111111111111/VAD",
                "injected_value": b"     2.97",
                "result": "3.0",
                "unit": VOLT,
                "class": DEVICE_CLASS_VOLTAGE,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_voltage_vdd",
                "unique_id": "/26.111111111111/VDD",
                "injected_value": b"    4.74",
                "result": "4.7",
                "unit": VOLT,
                "class": DEVICE_CLASS_VOLTAGE,
                "disabled": True,
            },
            {
                "entity_id": "sensor.26_111111111111_current",
                "unique_id": "/26.111111111111/IAD",
                "injected_value": b"       1",
                "result": "1.0",
                "unit": ELECTRICAL_CURRENT_AMPERE,
                "class": DEVICE_CLASS_CURRENT,
                "disabled": True,
            },
        ],
    },
    "28.111111111111": {
        "inject_reads": [
            b"DS18B20",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "28.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS18B20",
            "name": "28.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.28_111111111111_temperature",
                "unique_id": "/28.111111111111/temperature",
                "injected_value": b"    26.984",
                "result": "27.0",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "29.111111111111": {
        "inject_reads": [
            b"DS2408",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "29.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS2408",
            "name": "29.111111111111",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_0",
                "unique_id": "/29.111111111111/sensed.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_1",
                "unique_id": "/29.111111111111/sensed.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_2",
                "unique_id": "/29.111111111111/sensed.2",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_3",
                "unique_id": "/29.111111111111/sensed.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_4",
                "unique_id": "/29.111111111111/sensed.4",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_5",
                "unique_id": "/29.111111111111/sensed.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_6",
                "unique_id": "/29.111111111111/sensed.6",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "binary_sensor.29_111111111111_sensed_7",
                "unique_id": "/29.111111111111/sensed.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
        SWITCH_DOMAIN: [
            {
                "entity_id": "switch.29_111111111111_pio_0",
                "unique_id": "/29.111111111111/PIO.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_1",
                "unique_id": "/29.111111111111/PIO.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_2",
                "unique_id": "/29.111111111111/PIO.2",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_3",
                "unique_id": "/29.111111111111/PIO.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_4",
                "unique_id": "/29.111111111111/PIO.4",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_5",
                "unique_id": "/29.111111111111/PIO.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_6",
                "unique_id": "/29.111111111111/PIO.6",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_pio_7",
                "unique_id": "/29.111111111111/PIO.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_0",
                "unique_id": "/29.111111111111/latch.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_1",
                "unique_id": "/29.111111111111/latch.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_2",
                "unique_id": "/29.111111111111/latch.2",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_3",
                "unique_id": "/29.111111111111/latch.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_4",
                "unique_id": "/29.111111111111/latch.4",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_5",
                "unique_id": "/29.111111111111/latch.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_6",
                "unique_id": "/29.111111111111/latch.6",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.29_111111111111_latch_7",
                "unique_id": "/29.111111111111/latch.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
    },
    "3B.111111111111": {
        "inject_reads": [
            b"DS1825",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "3B.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS1825",
            "name": "3B.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.3b_111111111111_temperature",
                "unique_id": "/3B.111111111111/temperature",
                "injected_value": b"    28.243",
                "result": "28.2",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "42.111111111111": {
        "inject_reads": [
            b"DS28EA00",  # read device type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "42.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "DS28EA00",
            "name": "42.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.42_111111111111_temperature",
                "unique_id": "/42.111111111111/temperature",
                "injected_value": b"    29.123",
                "result": "29.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "EF.111111111111": {
        "inject_reads": [
            b"HobbyBoards_EF",  # read type
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "EF.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "HobbyBoards_EF",
            "name": "EF.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.ef_111111111111_humidity",
                "unique_id": "/EF.111111111111/humidity/humidity_corrected",
                "injected_value": b"    67.745",
                "result": "67.7",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111111_humidity_raw",
                "unique_id": "/EF.111111111111/humidity/humidity_raw",
                "injected_value": b"    65.541",
                "result": "65.5",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111111_temperature",
                "unique_id": "/EF.111111111111/humidity/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "EF.111111111112": {
        "inject_reads": [
            b"HB_MOISTURE_METER",  # read type
            b"         1",  # read is_leaf_0
            b"         1",  # read is_leaf_1
            b"         0",  # read is_leaf_2
            b"         0",  # read is_leaf_3
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "EF.111111111112")},
            "manufacturer": "Maxim Integrated",
            "model": "HB_MOISTURE_METER",
            "name": "EF.111111111112",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.ef_111111111112_wetness_0",
                "unique_id": "/EF.111111111112/moisture/sensor.0",
                "injected_value": b"    41.745",
                "result": "41.7",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111112_wetness_1",
                "unique_id": "/EF.111111111112/moisture/sensor.1",
                "injected_value": b"    42.541",
                "result": "42.5",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_2",
                "unique_id": "/EF.111111111112/moisture/sensor.2",
                "injected_value": b"    43.123",
                "result": "43.1",
                "unit": PRESSURE_CBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_3",
                "unique_id": "/EF.111111111112/moisture/sensor.3",
                "injected_value": b"    44.123",
                "result": "44.1",
                "unit": PRESSURE_CBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
        ],
    },
    "7E.111111111111": {
        "inject_reads": [
            b"EDS",  # read type
            b"EDS0068",  # read device_type - note EDS specific
        ],
        "device_info": {
            "identifiers": {(DOMAIN, "7E.111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "EDS",
            "name": "7E.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.7e_111111111111_temperature",
                "unique_id": "/7E.111111111111/EDS0068/temperature",
                "injected_value": b"    13.9375",
                "result": "13.9",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.7e_111111111111_pressure",
                "unique_id": "/7E.111111111111/EDS0068/pressure",
                "injected_value": b"  1012.21",
                "result": "1012.2",
                "unit": PRESSURE_MBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
            {
                "entity_id": "sensor.7e_111111111111_illuminance",
                "unique_id": "/7E.111111111111/EDS0068/light",
                "injected_value": b"  65.8839",
                "result": "65.9",
                "unit": LIGHT_LUX,
                "class": DEVICE_CLASS_ILLUMINANCE,
            },
            {
                "entity_id": "sensor.7e_111111111111_humidity",
                "unique_id": "/7E.111111111111/EDS0068/humidity",
                "injected_value": b"    41.375",
                "result": "41.4",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
        ],
    },
}

MOCK_SYSBUS_DEVICES = {
    "00-111111111111": {"sensors": []},
    "10-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "10-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "10",
            "name": "10-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.my_ds18b20_temperature",
                "unique_id": "/sys/bus/w1/devices/10-111111111111/w1_slave",
                "injected_value": 25.123,
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "12-111111111111": {"sensors": []},
    "1D-111111111111": {"sensors": []},
    "22-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "22-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "22",
            "name": "22-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.22_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/22-111111111111/w1_slave",
                "injected_value": FileNotFoundError,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "26-111111111111": {"sensors": []},
    "28-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "28-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "28",
            "name": "28-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.28_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/28-111111111111/w1_slave",
                "injected_value": InvalidCRCException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "29-111111111111": {"sensors": []},
    "3B-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "3B-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "3B",
            "name": "3B-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.3b_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/3B-111111111111/w1_slave",
                "injected_value": 29.993,
                "result": "30.0",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "42-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "42-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "42",
            "name": "42-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.42_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/42-111111111111/w1_slave",
                "injected_value": UnsupportResponseException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "EF-111111111111": {
        "sensors": [],
    },
    "EF-111111111112": {
        "sensors": [],
    },
}
