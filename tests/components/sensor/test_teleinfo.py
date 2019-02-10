"""The tests for the teleinfo platform."""

import json
import unittest
# from unittest import mock
from unittest.mock import patch

from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant, load_fixture)


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
