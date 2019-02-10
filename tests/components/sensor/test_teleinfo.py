"""The tests for the teleinfo platform."""

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'teleinfo',
        'device': '/dev/ttyACM0',
    }
}

VALID_CONFIG_NAME = {
    'sensor': {
        'platform': 'teleinfo',
        'name': 'edf',
        'device': '/dev/ttyUSB0',
    }
}
