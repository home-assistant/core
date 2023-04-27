"""Constants for 1-Wire integration."""
from pyownet.protocol import Error as ProtocolError

from homeassistant.components.onewire.const import Platform
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)

ATTR_DEVICE_FILE = "device_file"
ATTR_ENTITY_CATEGORY = "entity_category"
ATTR_INJECT_READS = "inject_reads"
ATTR_UNIQUE_ID = "unique_id"

FIXED_ATTRIBUTES = (
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)


MOCK_OWPROXY_DEVICES = {
    "00.111111111111": {
        ATTR_INJECT_READS: [
            b"",  # read device type
        ],
    },
    "05.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2405",  # read device type
        ],
        Platform.SWITCH: [
            {
                ATTR_INJECT_READS: b"    1",
            },
        ],
    },
    "10.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18S20",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "12.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2406",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_INJECT_READS: b"  1025.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
    },
    "1D.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2423",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    251123",
                ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: "count",
            },
            {
                ATTR_INJECT_READS: b"    248125",
                ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: "count",
            },
        ],
    },
    "1F.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2409",  # read device type
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
                            ATTR_INJECT_READS: b"    251123",
                            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                            ATTR_UNIT_OF_MEASUREMENT: "count",
                        },
                        {
                            ATTR_DEVICE_FILE: "/1F.111111111111/main/1D.111111111111/counter.B",
                            ATTR_INJECT_READS: b"    248125",
                            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
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
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: ProtocolError,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "26.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2438",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_INJECT_READS: b"    72.7563",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    73.7563",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    74.7563",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    75.7563",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: ProtocolError,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    969.265",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
            {
                ATTR_INJECT_READS: b"    65.8839",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
            },
            {
                ATTR_INJECT_READS: b"     2.97",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_INJECT_READS: b"    4.74",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_INJECT_READS: b"    0.12",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"    1",
            },
        ],
    },
    "28.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "28.222222222222": {
        # This device has precision options in the config entry
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_DEVICE_FILE: "/28.222222222222/temperature9",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "28.222222222223": {
        # This device has an illegal precision option in the config entry
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_DEVICE_FILE: "/28.222222222223/temperature",
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "29.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2408",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
    },
    "30.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2760",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    26.984",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_DEVICE_FILE: "/30.111111111111/typeK/temperature",
                ATTR_INJECT_READS: b"    173.7563",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_INJECT_READS: b"     2.97",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
            {
                ATTR_INJECT_READS: b"    0.12",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
            },
        ],
    },
    "3A.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2413",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_INJECT_READS: b"    1",
            },
            {
                ATTR_INJECT_READS: b"    0",
            },
        ],
    },
    "3B.111111111111": {
        ATTR_INJECT_READS: [
            b"DS1825",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    28.243",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "42.111111111111": {
        ATTR_INJECT_READS: [
            b"DS28EA00",  # read device type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    29.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ],
    },
    "EF.111111111111": {
        ATTR_INJECT_READS: [
            b"HobbyBoards_EF",  # read type
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    67.745",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    65.541",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    25.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
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
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    41.745",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    42.541",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_INJECT_READS: b"    43.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.CBAR,
            },
            {
                ATTR_INJECT_READS: b"    44.123",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.CBAR,
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
        ],
    },
    "EF.111111111113": {
        ATTR_INJECT_READS: [
            b"HB_HUB",  # read type
        ],
        Platform.BINARY_SENSOR: [
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_INJECT_READS: b"0",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                ATTR_INJECT_READS: b"0",
            },
        ],
        Platform.SWITCH: [
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"1",
            },
            {
                ATTR_ENTITY_CATEGORY: EntityCategory.CONFIG,
                ATTR_INJECT_READS: b"0",
            },
        ],
    },
    "7E.111111111111": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0068",  # read device_type - note EDS specific
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    13.9375",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_INJECT_READS: b"  1012.21",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
            {
                ATTR_INJECT_READS: b"  65.8839",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX,
            },
            {
                ATTR_INJECT_READS: b"    41.375",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
        ],
    },
    "7E.222222222222": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0066",  # read device_type - note EDS specific
        ],
        Platform.SENSOR: [
            {
                ATTR_INJECT_READS: b"    13.9375",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
            {
                ATTR_INJECT_READS: b"  1012.21",
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.MBAR,
            },
        ],
    },
}
