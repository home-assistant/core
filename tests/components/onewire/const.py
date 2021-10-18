"""Constants for 1-Wire integration."""
from pi1wire import InvalidCRCException, UnsupportResponseException
from pyownet.protocol import Error as ProtocolError

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.onewire.const import DOMAIN, PRESSURE_CBAR
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_MBAR,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
)

ATTR_DEFAULT_DISABLED = "default_disabled"
ATTR_UNIQUE_ID = "unique_id"

MANUFACTURER = "Maxim Integrated"

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
            ATTR_IDENTIFIERS: {(DOMAIN, "05.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2405",
            ATTR_NAME: "05.111111111111",
        },
        SWITCH_DOMAIN: [
            {
                ATTR_ENTITY_ID: "switch.05_111111111111_pio",
                ATTR_UNIQUE_ID: "/05.111111111111/PIO",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
    },
    "10.111111111111": {
        "inject_reads": [
            b"DS18S20",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "10.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS18S20",
            ATTR_NAME: "10.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.my_ds18b20_temperature",
                ATTR_UNIQUE_ID: "/10.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "12.111111111111": {
        "inject_reads": [
            b"DS2406",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "12.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2406",
            ATTR_NAME: "12.111111111111",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "binary_sensor.12_111111111111_sensed_a",
                ATTR_UNIQUE_ID: "/12.111111111111/sensed.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.12_111111111111_sensed_b",
                ATTR_UNIQUE_ID: "/12.111111111111/sensed.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.12_111111111111_temperature",
                ATTR_UNIQUE_ID: "/12.111111111111/TAI8570/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.12_111111111111_pressure",
                ATTR_UNIQUE_ID: "/12.111111111111/TAI8570/pressure",
                "injected_value": b"  1025.123",
                "result": "1025.1",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
        SWITCH_DOMAIN: [
            {
                ATTR_ENTITY_ID: "switch.12_111111111111_pio_a",
                ATTR_UNIQUE_ID: "/12.111111111111/PIO.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.12_111111111111_pio_b",
                ATTR_UNIQUE_ID: "/12.111111111111/PIO.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.12_111111111111_latch_a",
                ATTR_UNIQUE_ID: "/12.111111111111/latch.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.12_111111111111_latch_b",
                ATTR_UNIQUE_ID: "/12.111111111111/latch.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
    },
    "1D.111111111111": {
        "inject_reads": [
            b"DS2423",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "1D.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2423",
            ATTR_NAME: "1D.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_a",
                ATTR_UNIQUE_ID: "/1D.111111111111/counter.A",
                "injected_value": b"    251123",
                "result": "251123",
                ATTR_UNIT_OF_MEASUREMENT: "count",
                ATTR_DEVICE_CLASS: None,
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            },
            {
                ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_b",
                ATTR_UNIQUE_ID: "/1D.111111111111/counter.B",
                "injected_value": b"    248125",
                "result": "248125",
                ATTR_UNIT_OF_MEASUREMENT: "count",
                ATTR_DEVICE_CLASS: None,
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            },
        ],
    },
    "1F.111111111111": {
        "inject_reads": [
            b"DS2409",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "1F.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2409",
            ATTR_NAME: "1F.111111111111",
        },
        "branches": {
            "aux": {},
            "main": {
                "1D.111111111111": {
                    "inject_reads": [
                        b"DS2423",  # read device type
                    ],
                    "device_info": {
                        ATTR_IDENTIFIERS: {(DOMAIN, "1D.111111111111")},
                        ATTR_MANUFACTURER: MANUFACTURER,
                        ATTR_MODEL: "DS2423",
                        ATTR_NAME: "1D.111111111111",
                    },
                    SENSOR_DOMAIN: [
                        {
                            ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_a",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.A",
                            ATTR_UNIQUE_ID: "/1D.111111111111/counter.A",
                            "injected_value": b"    251123",
                            "result": "251123",
                            ATTR_UNIT_OF_MEASUREMENT: "count",
                            ATTR_DEVICE_CLASS: None,
                            ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                        },
                        {
                            ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_b",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.B",
                            ATTR_UNIQUE_ID: "/1D.111111111111/counter.B",
                            "injected_value": b"    248125",
                            "result": "248125",
                            ATTR_UNIT_OF_MEASUREMENT: "count",
                            ATTR_DEVICE_CLASS: None,
                            ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
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
            ATTR_IDENTIFIERS: {(DOMAIN, "22.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS1822",
            ATTR_NAME: "22.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.22_111111111111_temperature",
                ATTR_UNIQUE_ID: "/22.111111111111/temperature",
                "injected_value": ProtocolError,
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "26.111111111111": {
        "inject_reads": [
            b"DS2438",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "26.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2438",
            ATTR_NAME: "26.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_temperature",
                ATTR_UNIQUE_ID: "/26.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity",
                ATTR_UNIQUE_ID: "/26.111111111111/humidity",
                "injected_value": b"    72.7563",
                "result": "72.8",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity_hih3600",
                ATTR_UNIQUE_ID: "/26.111111111111/HIH3600/humidity",
                "injected_value": b"    73.7563",
                "result": "73.8",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity_hih4000",
                ATTR_UNIQUE_ID: "/26.111111111111/HIH4000/humidity",
                "injected_value": b"    74.7563",
                "result": "74.8",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity_hih5030",
                ATTR_UNIQUE_ID: "/26.111111111111/HIH5030/humidity",
                "injected_value": b"    75.7563",
                "result": "75.8",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity_htm1735",
                ATTR_UNIQUE_ID: "/26.111111111111/HTM1735/humidity",
                "injected_value": ProtocolError,
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_pressure",
                ATTR_UNIQUE_ID: "/26.111111111111/B1-R1-A/pressure",
                "injected_value": b"    969.265",
                "result": "969.3",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_illuminance",
                ATTR_UNIQUE_ID: "/26.111111111111/S3-R1-A/illuminance",
                "injected_value": b"    65.8839",
                "result": "65.9",
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_voltage_vad",
                ATTR_UNIQUE_ID: "/26.111111111111/VAD",
                "injected_value": b"     2.97",
                "result": "3.0",
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_voltage_vdd",
                ATTR_UNIQUE_ID: "/26.111111111111/VDD",
                "injected_value": b"    4.74",
                "result": "4.7",
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.26_111111111111_current",
                ATTR_UNIQUE_ID: "/26.111111111111/IAD",
                "injected_value": b"       1",
                "result": "1.0",
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
                ATTR_DEFAULT_DISABLED: True,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "28.111111111111": {
        "inject_reads": [
            b"DS18B20",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "28.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS18B20",
            ATTR_NAME: "28.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.28_111111111111_temperature",
                ATTR_UNIQUE_ID: "/28.111111111111/temperature",
                "injected_value": b"    26.984",
                "result": "27.0",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "29.111111111111": {
        "inject_reads": [
            b"DS2408",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "29.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2408",
            ATTR_NAME: "29.111111111111",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_0",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_1",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_2",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.2",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_3",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_4",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.4",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_5",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_6",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.6",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_7",
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
        SWITCH_DOMAIN: [
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_0",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_1",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_2",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.2",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_3",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_4",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.4",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_5",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_6",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.6",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_pio_7",
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_0",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.0",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_1",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.1",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_2",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.2",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_3",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.3",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_4",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.4",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_5",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.5",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_6",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.6",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_7",
                ATTR_UNIQUE_ID: "/29.111111111111/latch.7",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
    },
    "3A.111111111111": {
        "inject_reads": [
            b"DS2413",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "3A.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS2413",
            ATTR_NAME: "3A.111111111111",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "binary_sensor.3a_111111111111_sensed_a",
                ATTR_UNIQUE_ID: "/3A.111111111111/sensed.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "binary_sensor.3a_111111111111_sensed_b",
                ATTR_UNIQUE_ID: "/3A.111111111111/sensed.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
        SWITCH_DOMAIN: [
            {
                ATTR_ENTITY_ID: "switch.3a_111111111111_pio_a",
                ATTR_UNIQUE_ID: "/3A.111111111111/PIO.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
            {
                ATTR_ENTITY_ID: "switch.3a_111111111111_pio_b",
                ATTR_UNIQUE_ID: "/3A.111111111111/PIO.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                ATTR_UNIT_OF_MEASUREMENT: None,
                ATTR_DEVICE_CLASS: None,
                ATTR_DEFAULT_DISABLED: True,
            },
        ],
    },
    "3B.111111111111": {
        "inject_reads": [
            b"DS1825",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "3B.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS1825",
            ATTR_NAME: "3B.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.3b_111111111111_temperature",
                ATTR_UNIQUE_ID: "/3B.111111111111/temperature",
                "injected_value": b"    28.243",
                "result": "28.2",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "42.111111111111": {
        "inject_reads": [
            b"DS28EA00",  # read device type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "42.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "DS28EA00",
            ATTR_NAME: "42.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.42_111111111111_temperature",
                ATTR_UNIQUE_ID: "/42.111111111111/temperature",
                "injected_value": b"    29.123",
                "result": "29.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "EF.111111111111": {
        "inject_reads": [
            b"HobbyBoards_EF",  # read type
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "EF.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "HobbyBoards_EF",
            ATTR_NAME: "EF.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111111_humidity",
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/humidity_corrected",
                "injected_value": b"    67.745",
                "result": "67.7",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111111_humidity_raw",
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/humidity_raw",
                "injected_value": b"    65.541",
                "result": "65.5",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111111_temperature",
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
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
            ATTR_IDENTIFIERS: {(DOMAIN, "EF.111111111112")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "HB_MOISTURE_METER",
            ATTR_NAME: "EF.111111111112",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111112_wetness_0",
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.0",
                "injected_value": b"    41.745",
                "result": "41.7",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111112_wetness_1",
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.1",
                "injected_value": b"    42.541",
                "result": "42.5",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111112_moisture_2",
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.2",
                "injected_value": b"    43.123",
                "result": "43.1",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_CBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.ef_111111111112_moisture_3",
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.3",
                "injected_value": b"    44.123",
                "result": "44.1",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_CBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "7E.111111111111": {
        "inject_reads": [
            b"EDS",  # read type
            b"EDS0068",  # read device_type - note EDS specific
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "7E.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "EDS",
            ATTR_NAME: "7E.111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.7e_111111111111_temperature",
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/temperature",
                "injected_value": b"    13.9375",
                "result": "13.9",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.7e_111111111111_pressure",
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/pressure",
                "injected_value": b"  1012.21",
                "result": "1012.2",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.7e_111111111111_illuminance",
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/light",
                "injected_value": b"  65.8839",
                "result": "65.9",
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.7e_111111111111_humidity",
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/humidity",
                "injected_value": b"    41.375",
                "result": "41.4",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "7E.222222222222": {
        "inject_reads": [
            b"EDS",  # read type
            b"EDS0066",  # read device_type - note EDS specific
        ],
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "7E.222222222222")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "EDS",
            ATTR_NAME: "7E.222222222222",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.7e_222222222222_temperature",
                ATTR_UNIQUE_ID: "/7E.222222222222/EDS0066/temperature",
                "injected_value": b"    13.9375",
                "result": "13.9",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
            {
                ATTR_ENTITY_ID: "sensor.7e_222222222222_pressure",
                ATTR_UNIQUE_ID: "/7E.222222222222/EDS0066/pressure",
                "injected_value": b"  1012.21",
                "result": "1012.2",
                ATTR_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
}

MOCK_SYSBUS_DEVICES = {
    "00-111111111111": {SENSOR_DOMAIN: []},
    "10-111111111111": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "10-111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "10",
            ATTR_NAME: "10-111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.my_ds18b20_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/10-111111111111/w1_slave",
                "injected_value": 25.123,
                "result": "25.1",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "12-111111111111": {SENSOR_DOMAIN: []},
    "1D-111111111111": {SENSOR_DOMAIN: []},
    "22-111111111111": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "22-111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "22",
            ATTR_NAME: "22-111111111111",
        },
        "sensor": [
            {
                ATTR_ENTITY_ID: "sensor.22_111111111111_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/22-111111111111/w1_slave",
                "injected_value": FileNotFoundError,
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "26-111111111111": {SENSOR_DOMAIN: []},
    "28-111111111111": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "28-111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "28",
            ATTR_NAME: "28-111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.28_111111111111_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/28-111111111111/w1_slave",
                "injected_value": InvalidCRCException,
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "29-111111111111": {SENSOR_DOMAIN: []},
    "3A-111111111111": {SENSOR_DOMAIN: []},
    "3B-111111111111": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "3B-111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "3B",
            ATTR_NAME: "3B-111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.3b_111111111111_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/3B-111111111111/w1_slave",
                "injected_value": 29.993,
                "result": "30.0",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "42-111111111111": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "42-111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "42",
            ATTR_NAME: "42-111111111111",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.42_111111111111_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/42-111111111111/w1_slave",
                "injected_value": UnsupportResponseException,
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "42-111111111112": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "42-111111111112")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "42",
            ATTR_NAME: "42-111111111112",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.42_111111111112_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/42-111111111112/w1_slave",
                "injected_value": [UnsupportResponseException] * 9 + [27.993],
                "result": "28.0",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "42-111111111113": {
        "device_info": {
            ATTR_IDENTIFIERS: {(DOMAIN, "42-111111111113")},
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: "42",
            ATTR_NAME: "42-111111111113",
        },
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.42_111111111113_temperature",
                ATTR_UNIQUE_ID: "/sys/bus/w1/devices/42-111111111113/w1_slave",
                "injected_value": [UnsupportResponseException] * 10 + [27.993],
                "result": "unknown",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            },
        ],
    },
    "EF-111111111111": {
        SENSOR_DOMAIN: [],
    },
    "EF-111111111112": {
        SENSOR_DOMAIN: [],
    },
}
