"""Constants for 1-Wire integration."""
from pyownet.protocol import Error as ProtocolError

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.onewire.const import (
    DOMAIN,
    MANUFACTURER_EDS,
    MANUFACTURER_HOBBYBOARDS,
    MANUFACTURER_MAXIM,
    Platform,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_VIA_DEVICE,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)

ATTR_DEFAULT_DISABLED = "default_disabled"
ATTR_DEVICE_FILE = "device_file"
ATTR_DEVICE_INFO = "device_info"
ATTR_ENTITY_CATEGORY = "entity_category"
ATTR_INJECT_READS = "inject_reads"
ATTR_UNIQUE_ID = "unique_id"
ATTR_UNKNOWN_DEVICE = "unknown_device"

FIXED_ATTRIBUTES = (
    ATTR_DEVICE_CLASS,
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)


MOCK_OWPROXY_DEVICES = {
    "00.111111111111": {
        ATTR_INJECT_READS: [
            b"",  # read device type
        ],
        ATTR_UNKNOWN_DEVICE: True,
    },
    "05.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2405",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "05.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2405",
            ATTR_NAME: "05.111111111111",
        },
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.05_111111111111_programmed_input_output",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/05.111111111111/PIO",
            },
        ],
    },
    "10.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18S20",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "10.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS18S20",
            ATTR_NAME: "10.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.10_111111111111_temperature",
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE: "25.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/10.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "12.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2406",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "12.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2406",
            ATTR_NAME: "12.111111111111",
        },
        Platform.BINARY_SENSOR: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.12_111111111111_sensed_a",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/12.111111111111/sensed.A",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.12_111111111111_sensed_b",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/12.111111111111/sensed.B",
            },
        ],
        Platform.SENSOR: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.12_111111111111_temperature",
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE: "25.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/12.111111111111/TAI8570/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.12_111111111111_pressure",
                ATTR_INJECT_READS: b"  1025.123",
                ATTR_STATE: "1025.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/12.111111111111/TAI8570/pressure",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.12_111111111111_programmed_input_output_a",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/12.111111111111/PIO.A",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.12_111111111111_programmed_input_output_b",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/12.111111111111/PIO.B",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.12_111111111111_latch_a",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/12.111111111111/latch.A",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.12_111111111111_latch_b",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/12.111111111111/latch.B",
            },
        ],
    },
    "1D.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2423",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "1D.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2423",
            ATTR_NAME: "1D.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_a",
                ATTR_INJECT_READS: b"    251123",
                ATTR_STATE: "251123",
                ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "/1D.111111111111/counter.A",
                ATTR_UNIT_OF_MEASUREMENT: "count",
            },
            {
                ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_b",
                ATTR_INJECT_READS: b"    248125",
                ATTR_STATE: "248125",
                ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "/1D.111111111111/counter.B",
                ATTR_UNIT_OF_MEASUREMENT: "count",
            },
        ],
    },
    "1F.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2409",  # read device type
        ],
        ATTR_DEVICE_INFO: [
            {
                ATTR_IDENTIFIERS: {(DOMAIN, "1F.111111111111")},
                ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
                ATTR_MODEL: "DS2409",
                ATTR_NAME: "1F.111111111111",
            },
            {
                ATTR_IDENTIFIERS: {(DOMAIN, "1D.111111111111")},
                ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
                ATTR_MODEL: "DS2423",
                ATTR_NAME: "1D.111111111111",
                ATTR_VIA_DEVICE: (DOMAIN, "1F.111111111111"),
            },
        ],
        "branches": {
            "aux": {},
            "main": {
                "1D.111111111111": {
                    ATTR_INJECT_READS: [
                        b"DS2423",  # read device type
                    ],
                    Platform.SENSOR: [
                        {
                            ATTR_DEVICE_FILE: "/1F.111111111111/main/1D.111111111111/counter.A",
                            ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_a",
                            ATTR_INJECT_READS: b"    251123",
                            ATTR_STATE: "251123",
                            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                            ATTR_UNIQUE_ID: "/1D.111111111111/counter.A",
                            ATTR_UNIT_OF_MEASUREMENT: "count",
                        },
                        {
                            ATTR_DEVICE_FILE: "/1F.111111111111/main/1D.111111111111/counter.B",
                            ATTR_ENTITY_ID: "sensor.1d_111111111111_counter_b",
                            ATTR_INJECT_READS: b"    248125",
                            ATTR_STATE: "248125",
                            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                            ATTR_UNIQUE_ID: "/1D.111111111111/counter.B",
                            ATTR_UNIT_OF_MEASUREMENT: "count",
                        },
                    ],
                },
            },
        },
    },
    "22.111111111111": {
        ATTR_INJECT_READS: [
            b"DS1822",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "22.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS1822",
            ATTR_NAME: "22.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.22_111111111111_temperature",
                ATTR_INJECT_READS: ProtocolError,
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/22.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "26.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2438",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "26.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2438",
            ATTR_NAME: "26.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_temperature",
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE: "25.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.26_111111111111_humidity",
                ATTR_INJECT_READS: b"    72.7563",
                ATTR_STATE: "72.8",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.26_111111111111_hih3600_humidity",
                ATTR_INJECT_READS: b"    73.7563",
                ATTR_STATE: "73.8",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/HIH3600/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.26_111111111111_hih4000_humidity",
                ATTR_INJECT_READS: b"    74.7563",
                ATTR_STATE: "74.8",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/HIH4000/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.26_111111111111_hih5030_humidity",
                ATTR_INJECT_READS: b"    75.7563",
                ATTR_STATE: "75.8",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/HIH5030/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.26_111111111111_htm1735_humidity",
                ATTR_INJECT_READS: ProtocolError,
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/HTM1735/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_pressure",
                ATTR_INJECT_READS: b"    969.265",
                ATTR_STATE: "969.3",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/B1-R1-A/pressure",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.ILLUMINANCE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_illuminance",
                ATTR_INJECT_READS: b"    65.8839",
                ATTR_STATE: "65.9",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/S3-R1-A/illuminance",
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_vad_voltage",
                ATTR_INJECT_READS: b"     2.97",
                ATTR_STATE: "3.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/VAD",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_vdd_voltage",
                ATTR_INJECT_READS: b"    4.74",
                ATTR_STATE: "4.7",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/VDD",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
                ATTR_ENTITY_ID: "sensor.26_111111111111_vis_voltage_difference",
                ATTR_INJECT_READS: b"    0.12",
                ATTR_STATE: "0.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/26.111111111111/vis",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.26_111111111111_current_a_d_control",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/26.111111111111/IAD",
            },
        ],
    },
    "28.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "28.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS18B20",
            ATTR_NAME: "28.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.28_111111111111_temperature",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE: "27.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/28.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "28.222222222222": {
        # This device has precision options in the config entry
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "28.222222222222")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS18B20",
            ATTR_NAME: "28.222222222222",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_DEVICE_FILE: "/28.222222222222/temperature9",
                ATTR_ENTITY_ID: "sensor.28_222222222222_temperature",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE: "27.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/28.222222222222/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "28.222222222223": {
        # This device has an illegal precision option in the config entry
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "28.222222222223")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS18B20",
            ATTR_NAME: "28.222222222223",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_DEVICE_FILE: "/28.222222222223/temperature",
                ATTR_ENTITY_ID: "sensor.28_222222222223_temperature",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE: "27.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/28.222222222223/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "29.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2408",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "29.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2408",
            ATTR_NAME: "29.111111111111",
        },
        Platform.BINARY_SENSOR: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_0",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_1",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_2",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_3",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.3",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_4",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.4",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_5",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.5",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_6",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.6",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.29_111111111111_sensed_7",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/sensed.7",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_0",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_1",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_2",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_3",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.3",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_4",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.4",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_5",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.5",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_6",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.6",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_programmed_input_output_7",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/PIO.7",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_0",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_1",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_2",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_3",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.3",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_4",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.4",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_5",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.5",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_6",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.6",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.29_111111111111_latch_7",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/29.111111111111/latch.7",
            },
        ],
    },
    "30.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2760",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "30.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2760",
            ATTR_NAME: "30.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.30_111111111111_temperature",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE: "27.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/30.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_DEVICE_FILE: "/30.111111111111/typeK/temperature",
                ATTR_ENTITY_ID: "sensor.30_111111111111_thermocouple_k_temperature",
                ATTR_INJECT_READS: b"    173.7563",
                ATTR_STATE: "173.8",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/30.111111111111/typeX/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
                ATTR_ENTITY_ID: "sensor.30_111111111111_voltage",
                ATTR_INJECT_READS: b"     2.97",
                ATTR_STATE: "3.0",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/30.111111111111/volt",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
                ATTR_ENTITY_ID: "sensor.30_111111111111_vis_voltage_gradient",
                ATTR_INJECT_READS: b"    0.12",
                ATTR_STATE: "0.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/30.111111111111/vis",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
        ],
    },
    "3A.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2413",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "3A.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS2413",
            ATTR_NAME: "3A.111111111111",
        },
        Platform.BINARY_SENSOR: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.3a_111111111111_sensed_a",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/3A.111111111111/sensed.A",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "binary_sensor.3a_111111111111_sensed_b",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/3A.111111111111/sensed.B",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.3a_111111111111_programmed_input_output_a",
                ATTR_INJECT_READS: b"    1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/3A.111111111111/PIO.A",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_ID: "switch.3a_111111111111_programmed_input_output_b",
                ATTR_INJECT_READS: b"    0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/3A.111111111111/PIO.B",
            },
        ],
    },
    "3B.111111111111": {
        ATTR_INJECT_READS: [
            b"DS1825",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "3B.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS1825",
            ATTR_NAME: "3B.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.3b_111111111111_temperature",
                ATTR_INJECT_READS: b"    28.243",
                ATTR_STATE: "28.2",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/3B.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "42.111111111111": {
        ATTR_INJECT_READS: [
            b"DS28EA00",  # read device type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "42.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_MAXIM,
            ATTR_MODEL: "DS28EA00",
            ATTR_NAME: "42.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.42_111111111111_temperature",
                ATTR_INJECT_READS: b"    29.123",
                ATTR_STATE: "29.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/42.111111111111/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "EF.111111111111": {
        ATTR_INJECT_READS: [
            b"HobbyBoards_EF",  # read type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "EF.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_HOBBYBOARDS,
            ATTR_MODEL: "HobbyBoards_EF",
            ATTR_NAME: "EF.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.ef_111111111111_humidity",
                ATTR_INJECT_READS: b"    67.745",
                ATTR_STATE: "67.7",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/humidity_corrected",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.ef_111111111111_raw_humidity",
                ATTR_INJECT_READS: b"    65.541",
                ATTR_STATE: "65.5",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/humidity_raw",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.ef_111111111111_temperature",
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE: "25.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111111/humidity/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "EF.111111111112": {
        ATTR_INJECT_READS: [
            b"HB_MOISTURE_METER",  # read type
            b"         1",  # read is_leaf_0
            b"         1",  # read is_leaf_1
            b"         0",  # read is_leaf_2
            b"         0",  # read is_leaf_3
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "EF.111111111112")},
            ATTR_MANUFACTURER: MANUFACTURER_HOBBYBOARDS,
            ATTR_MODEL: "HB_MOISTURE_METER",
            ATTR_NAME: "EF.111111111112",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.ef_111111111112_wetness_0",
                ATTR_INJECT_READS: b"    41.745",
                ATTR_STATE: "41.7",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.0",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.ef_111111111112_wetness_1",
                ATTR_INJECT_READS: b"    42.541",
                ATTR_STATE: "42.5",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.1",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.ef_111111111112_moisture_2",
                ATTR_INJECT_READS: b"    43.123",
                ATTR_STATE: "43.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.2",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.CBAR,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.ef_111111111112_moisture_3",
                ATTR_INJECT_READS: b"    44.123",
                ATTR_STATE: "44.1",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/sensor.3",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.CBAR,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_leaf_sensor_0",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_leaf.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_leaf_sensor_1",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_leaf.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_leaf_sensor_2",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_leaf.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_leaf_sensor_3",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_leaf.3",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_moisture_sensor_0",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_moisture.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_moisture_sensor_1",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_moisture.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_moisture_sensor_2",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_moisture.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111112_moisture_sensor_3",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111112/moisture/is_moisture.3",
            },
        ],
    },
    "EF.111111111113": {
        ATTR_INJECT_READS: [
            b"HB_HUB",  # read type
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "EF.111111111113")},
            ATTR_MANUFACTURER: MANUFACTURER_HOBBYBOARDS,
            ATTR_MODEL: "HB_HUB",
            ATTR_NAME: "EF.111111111113",
        },
        Platform.BINARY_SENSOR: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.PROBLEM,
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_ENTITY_ID: "binary_sensor.ef_111111111113_hub_short_on_branch_0",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/short.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.PROBLEM,
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_ENTITY_ID: "binary_sensor.ef_111111111113_hub_short_on_branch_1",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/short.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.PROBLEM,
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_ENTITY_ID: "binary_sensor.ef_111111111113_hub_short_on_branch_2",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/short.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.PROBLEM,
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_ENTITY_ID: "binary_sensor.ef_111111111113_hub_short_on_branch_3",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/short.3",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111113_hub_branch_0",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/branch.0",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111113_hub_branch_1",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/branch.1",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111113_hub_branch_2",
                ATTR_INJECT_READS: b"1",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/branch.2",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_ENTITY_ID: "switch.ef_111111111113_hub_branch_3",
                ATTR_INJECT_READS: b"0",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "/EF.111111111113/hub/branch.3",
            },
        ],
    },
    "7E.111111111111": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0068",  # read device_type - note EDS specific
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "7E.111111111111")},
            ATTR_MANUFACTURER: MANUFACTURER_EDS,
            ATTR_MODEL: "EDS0068",
            ATTR_NAME: "7E.111111111111",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.7e_111111111111_temperature",
                ATTR_INJECT_READS: b"    13.9375",
                ATTR_STATE: "13.9",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.7e_111111111111_pressure",
                ATTR_INJECT_READS: b"  1012.21",
                ATTR_STATE: "1012.2",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/pressure",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.ILLUMINANCE,
                ATTR_ENTITY_ID: "sensor.7e_111111111111_illuminance",
                ATTR_INJECT_READS: b"  65.8839",
                ATTR_STATE: "65.9",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/light",
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
                ATTR_ENTITY_ID: "sensor.7e_111111111111_humidity",
                ATTR_INJECT_READS: b"    41.375",
                ATTR_STATE: "41.4",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.111111111111/EDS0068/humidity",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
        ],
    },
    "7E.222222222222": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0066",  # read device_type - note EDS specific
        ],
        ATTR_DEVICE_INFO: {
            ATTR_IDENTIFIERS: {(DOMAIN, "7E.222222222222")},
            ATTR_MANUFACTURER: MANUFACTURER_EDS,
            ATTR_MODEL: "EDS0066",
            ATTR_NAME: "7E.222222222222",
        },
        Platform.SENSOR: [
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.7e_222222222222_temperature",
                ATTR_INJECT_READS: b"    13.9375",
                ATTR_STATE: "13.9",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.222222222222/EDS0066/temperature",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
                ATTR_ENTITY_ID: "sensor.7e_222222222222_pressure",
                ATTR_INJECT_READS: b"  1012.21",
                ATTR_STATE: "1012.2",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIQUE_ID: "/7E.222222222222/EDS0066/pressure",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
        ],
    },
}
