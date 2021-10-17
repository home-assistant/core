"""Configure py.test."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture(name="tomorrowio_config_flow_connect", autouse=True)
def tomorrowio_config_flow_connect():
    """Mock valid tomorrowio config flow setup."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        return_value={},
    ):
        yield


@pytest.fixture(name="tomorrowio_config_entry_update")
def tomorrowio_config_entry_update_fixture():
    """Mock valid tomorrowio config entry setup."""
    with patch(
        "homeassistant.components.tomorrowio.TomorrowioV4.realtime_and_all_forecasts",
        return_value=json.loads(load_fixture("tomorrowio/v4.json")),
    ):
        yield
