"""Constants for 1-Wire integration."""

from pyownet.protocol import ProtocolError

ATTR_INJECT_READS = "inject_reads"


MOCK_OWPROXY_DEVICES = {
    "00.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b""],
        },
    },
    "05.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2405"],
            "/PIO": [b"    1"],
        },
    },
    "10.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS18S20"],
            "/temperature": [b"    25.123"],
        },
    },
    "12.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2406"],
            # TAI8570 values are read twice:
            # - once during init to make sure TAI8570 is accessible
            # - once during first update to get the actual values
            "/TAI8570/temperature": [b"    25.123", b"    25.123"],
            "/TAI8570/pressure": [b"  1025.123", b"  1025.123"],
            "/PIO.A": [b"    1"],
            "/PIO.B": [b"    0"],
            "/latch.A": [b"    1"],
            "/latch.B": [b"    0"],
            "/sensed.A": [b"    1"],
            "/sensed.B": [b"    0"],
        },
    },
    "1D.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2423"],
            "/counter.A": [b"    251123"],
            "/counter.B": [b"    248125"],
        }
    },
    "16.111111111111": {
        # Test case for issue #115984, where the device type cannot be read
        ATTR_INJECT_READS: {"/type": [ProtocolError()]},
    },
    "1F.111111111111": {
        ATTR_INJECT_READS: {"/type": [b"DS2409"]},
        "branches": {
            "aux": {},
            "main": {
                "1D.111111111111": {
                    ATTR_INJECT_READS: {
                        "/type": [b"DS2423"],
                        "/counter.A": [b"    251123"],
                        "/counter.B": [b"    248125"],
                    },
                },
            },
        },
    },
    "22.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS1822"],
            "/temperature": [ProtocolError],
        },
    },
    "26.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2438"],
            "/temperature": [b"    25.123"],
            "/humidity": [b"    72.7563"],
            "/HIH3600/humidity": [b"    73.7563"],
            "/HIH4000/humidity": [b"    74.7563"],
            "/HIH5030/humidity": [b"    75.7563"],
            "/HTM1735/humidity": [ProtocolError],
            "/B1-R1-A/pressure": [b"    969.265"],
            "/S3-R1-A/illuminance": [b"    65.8839"],
            "/VAD": [b"     2.97"],
            "/VDD": [b"    4.74"],
            "/vis": [b"    0.12"],
            "/IAD": [b"    1"],
        },
    },
    "28.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS18B20"],
            "/temperature": [b"    26.984"],
            "/tempres": [b"    12"],
        },
    },
    "28.222222222222": {
        # This device has precision options in the config entry
        ATTR_INJECT_READS: {
            "/type": [b"DS18B20"],
            "/temperature9": [b"    26.984"],
        },
    },
    "28.222222222223": {
        # This device has an illegal precision option in the config entry
        ATTR_INJECT_READS: {
            "/type": [b"DS18B20"],
            "/temperature": [b"    26.984"],
        },
    },
    "29.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2408"],
            "/PIO.0": [b"    1"],
            "/PIO.1": [b"    0"],
            "/PIO.2": [b"    1"],
            "/PIO.3": [ProtocolError],
            "/PIO.4": [b"    1"],
            "/PIO.5": [b"    0"],
            "/PIO.6": [b"    1"],
            "/PIO.7": [b"    0"],
            "/latch.0": [b"    1"],
            "/latch.1": [b"    0"],
            "/latch.2": [b"    1"],
            "/latch.3": [b"    0"],
            "/latch.4": [b"    1"],
            "/latch.5": [b"    0"],
            "/latch.6": [b"    1"],
            "/latch.7": [b"    0"],
            "/sensed.0": [b"    1"],
            "/sensed.1": [b"    0"],
            "/sensed.2": [b"    0"],
            "/sensed.3": [ProtocolError],
            "/sensed.4": [b"    0"],
            "/sensed.5": [b"    0"],
            "/sensed.6": [b"    0"],
            "/sensed.7": [b"    0"],
        },
    },
    "30.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2760"],
            "/temperature": [b"    26.984"],
            "/typeK/temperature": [b"    173.7563"],
            "/volt": [b"     2.97"],
            "/vis": [b"     0.12"],
        },
    },
    "3A.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2413"],
            "/PIO.A": [b"    1"],
            "/PIO.B": [b"    0"],
            "/sensed.A": [b"    1"],
            "/sensed.B": [b"    0"],
        },
    },
    "3B.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS1825"],
            "/temperature": [b"    28.243"],
        },
    },
    "42.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS28EA00"],
            "/temperature": [b"    29.123"],
        },
    },
    "A6.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"DS2438"],
            "/temperature": [b"    25.123"],
            "/humidity": [b"    72.7563"],
            "/HIH3600/humidity": [b"    73.7563"],
            "/HIH4000/humidity": [b"    74.7563"],
            "/HIH5030/humidity": [b"    75.7563"],
            "/HTM1735/humidity": [ProtocolError],
            "/B1-R1-A/pressure": [b"    969.265"],
            "/S3-R1-A/illuminance": [b"    65.8839"],
            "/VAD": [b"     2.97"],
            "/VDD": [b"    4.74"],
            "/vis": [b"    0.12"],
            "/IAD": [b"    1"],
        },
    },
    "EF.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"HobbyBoards_EF"],
            "/humidity/humidity_corrected": [b"    67.745"],
            "/humidity/humidity_raw": [b"    65.541"],
            "/humidity/temperature": [b"    25.123"],
        },
    },
    "EF.111111111112": {
        ATTR_INJECT_READS: {
            "/type": [b"HB_MOISTURE_METER"],
            "/moisture/is_leaf.0": [b"         1"],
            "/moisture/is_leaf.1": [b"         1"],
            "/moisture/is_leaf.2": [b"         0"],
            "/moisture/is_leaf.3": [b"         0"],
            "/moisture/sensor.0": [b"    41.745"],
            "/moisture/sensor.1": [b"    42.541"],
            "/moisture/sensor.2": [b"    43.123"],
            "/moisture/sensor.3": [b"    44.123"],
            "/moisture/is_moisture.0": [b"    1"],
            "/moisture/is_moisture.1": [b"    1"],
            "/moisture/is_moisture.2": [b"    0"],
            "/moisture/is_moisture.3": [b"    0"],
        },
    },
    "EF.111111111113": {
        ATTR_INJECT_READS: {
            "/type": [b"HB_HUB"],
            "/hub/branch.0": [b"         1"],
            "/hub/branch.1": [b"         0"],
            "/hub/branch.2": [b"         1"],
            "/hub/branch.3": [b"         0"],
            "/hub/short.0": [b"         1"],
            "/hub/short.1": [b"         0"],
            "/hub/short.2": [b"         1"],
            "/hub/short.3": [b"         0"],
        },
    },
    "7E.111111111111": {
        ATTR_INJECT_READS: {
            "/type": [b"EDS"],
            "/device_type": [b"EDS0068"],
            "/EDS0068/temperature": [b"  13.9375"],
            "/EDS0068/pressure": [b"  1012.21"],
            "/EDS0068/light": [b"  65.8839"],
            "/EDS0068/humidity": [b"   41.375"],
        },
    },
    "7E.222222222222": {
        ATTR_INJECT_READS: {
            "/type": [b"EDS"],
            "/device_type": [b"EDS0066"],
            "/EDS0066/temperature": [b"    13.9375"],
            "/EDS0066/pressure": [b"  1012.21"],
        },
    },
}
