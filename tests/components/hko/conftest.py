"""Configure py.test."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture(name="hko_config_flow_connect", autouse=True)
def hko_config_flow_connect():
    """Mock valid config flow setup."""
    with patch(
        "homeassistant.components.hko.config_flow.HKO.weather",
        return_value=json.loads(load_fixture("hko/rhrread.json")),
    ):
        yield
