"""Configure py.test."""

from unittest.mock import patch

import pytest

from tests.common import load_json_object_fixture


@pytest.fixture(name="hko_config_flow_connect", autouse=True)
def hko_config_flow_connect():
    """Mock valid config flow setup."""
    with patch(
        "homeassistant.components.hko.config_flow.HKO.weather",
        return_value=load_json_object_fixture("hko/rhrread.json"),
    ):
        yield
