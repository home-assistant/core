"""Configure py.test."""
import json
from unittest.mock import PropertyMock, patch

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


@pytest.fixture(name="tomorrowio_config_entry_update", autouse=True)
def tomorrowio_config_entry_update_fixture():
    """Mock valid tomorrowio config entry setup."""
    with patch(
        "homeassistant.components.tomorrowio.TomorrowioV4.realtime_and_all_forecasts",
        return_value=json.loads(load_fixture("v4.json", "tomorrowio")),
    ) as mock_update, patch(
        "homeassistant.components.tomorrowio.TomorrowioV4.max_requests_per_day",
        new_callable=PropertyMock,
    ) as mock_max_requests_per_day, patch(
        "homeassistant.components.tomorrowio.TomorrowioV4.num_api_requests",
        new_callable=PropertyMock,
    ) as mock_num_api_requests:
        mock_max_requests_per_day.return_value = 100
        mock_num_api_requests.return_value = 2
        yield mock_update
