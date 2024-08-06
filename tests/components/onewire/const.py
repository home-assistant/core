"""Constants for 1-Wire integration."""

from pyownet.protocol import ProtocolError

from homeassistant.components.onewire.const import Platform

ATTR_DEVICE_FILE = "device_file"
ATTR_INJECT_READS = "inject_reads"


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
            {ATTR_INJECT_READS: b"    1"},
        ],
    },
    "10.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18S20",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    25.123"},
        ],
    },
    "12.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2406",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    25.123"},
            {ATTR_INJECT_READS: b"  1025.123"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
        ],
    },
    "1D.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2423",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    251123"},
            {ATTR_INJECT_READS: b"    248125"},
        ],
    },
    "16.111111111111": {
        # Test case for issue #115984, where the device type cannot be read
        ATTR_INJECT_READS: [
            ProtocolError(),  # read device type
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
                        },
                        {
                            ATTR_DEVICE_FILE: "/1F.111111111111/main/1D.111111111111/counter.B",
                            ATTR_INJECT_READS: b"    248125",
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
            },
        ],
    },
    "26.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2438",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    25.123"},
            {ATTR_INJECT_READS: b"    72.7563"},
            {ATTR_INJECT_READS: b"    73.7563"},
            {ATTR_INJECT_READS: b"    74.7563"},
            {ATTR_INJECT_READS: b"    75.7563"},
            {
                ATTR_INJECT_READS: ProtocolError,
            },
            {ATTR_INJECT_READS: b"    969.265"},
            {ATTR_INJECT_READS: b"    65.8839"},
            {ATTR_INJECT_READS: b"     2.97"},
            {ATTR_INJECT_READS: b"    4.74"},
            {ATTR_INJECT_READS: b"    0.12"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"    1"},
        ],
    },
    "28.111111111111": {
        ATTR_INJECT_READS: [
            b"DS18B20",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    26.984"},
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
            },
        ],
    },
    "29.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2408",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    0"},
            {
                ATTR_INJECT_READS: ProtocolError,
            },
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    0"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {
                ATTR_INJECT_READS: ProtocolError,
            },
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
        ],
    },
    "30.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2760",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    26.984"},
            {
                ATTR_DEVICE_FILE: "/30.111111111111/typeK/temperature",
                ATTR_INJECT_READS: b"    173.7563",
            },
            {ATTR_INJECT_READS: b"     2.97"},
            {ATTR_INJECT_READS: b"     0.12"},
        ],
    },
    "3A.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2413",  # read device type
        ],
        Platform.BINARY_SENSOR: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"    1"},
            {ATTR_INJECT_READS: b"    0"},
        ],
    },
    "3B.111111111111": {
        ATTR_INJECT_READS: [
            b"DS1825",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    28.243"},
        ],
    },
    "42.111111111111": {
        ATTR_INJECT_READS: [
            b"DS28EA00",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    29.123"},
        ],
    },
    "A6.111111111111": {
        ATTR_INJECT_READS: [
            b"DS2438",  # read device type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    25.123"},
            {ATTR_INJECT_READS: b"    72.7563"},
            {ATTR_INJECT_READS: b"    73.7563"},
            {ATTR_INJECT_READS: b"    74.7563"},
            {ATTR_INJECT_READS: b"    75.7563"},
            {
                ATTR_INJECT_READS: ProtocolError,
            },
            {ATTR_INJECT_READS: b"    969.265"},
            {ATTR_INJECT_READS: b"    65.8839"},
            {ATTR_INJECT_READS: b"     2.97"},
            {ATTR_INJECT_READS: b"    4.74"},
            {ATTR_INJECT_READS: b"    0.12"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"    1"},
        ],
    },
    "EF.111111111111": {
        ATTR_INJECT_READS: [
            b"HobbyBoards_EF",  # read type
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    67.745"},
            {ATTR_INJECT_READS: b"    65.541"},
            {ATTR_INJECT_READS: b"    25.123"},
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
            {ATTR_INJECT_READS: b"    41.745"},
            {ATTR_INJECT_READS: b"    42.541"},
            {ATTR_INJECT_READS: b"    43.123"},
            {ATTR_INJECT_READS: b"    44.123"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
            {ATTR_INJECT_READS: b"0"},
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
            {ATTR_INJECT_READS: b"0"},
        ],
    },
    "EF.111111111113": {
        ATTR_INJECT_READS: [
            b"HB_HUB",  # read type
        ],
        Platform.BINARY_SENSOR: [
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
        ],
        Platform.SWITCH: [
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
            {ATTR_INJECT_READS: b"1"},
            {ATTR_INJECT_READS: b"0"},
        ],
    },
    "7E.111111111111": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0068",  # read device_type - note EDS specific
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"  13.9375"},
            {ATTR_INJECT_READS: b"  1012.21"},
            {ATTR_INJECT_READS: b"  65.8839"},
            {ATTR_INJECT_READS: b"   41.375"},
        ],
    },
    "7E.222222222222": {
        ATTR_INJECT_READS: [
            b"EDS",  # read type
            b"EDS0066",  # read device_type - note EDS specific
        ],
        Platform.SENSOR: [
            {ATTR_INJECT_READS: b"    13.9375"},
            {ATTR_INJECT_READS: b"  1012.21"},
        ],
    },
}
