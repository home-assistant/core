"""Fixtures for emoncms integration tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.emoncms.const import (
    CONF_EXCLUDE_FEEDID,
    CONF_FEED_LIST,
    CONF_ONLY_INCLUDE_FEEDID,
    CONF_SENSOR_NAMES,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import template

from tests.common import MockConfigEntry

FEEDS = [
    {
        "id": "1",
        "userid": "1",
        "name": "Cellule_Tcircuit",
        "tag": " sofrel_circuit_Cellule",
        "public": "0",
        "size": "35811340",
        "engine": "5",
        "processList": "",
        "unit": "°C",
        "time": 1665509570,
        "value": 17.690000534058,
        "start_time": 1575981270,
        "end_time": 1665509570,
        "interval": 10,
        "npoints": 8952831,
    },
    {
        "id": "2",
        "userid": "1",
        "name": "Nord_Tcircuit",
        "tag": " sofrel_circuit_Nord",
        "public": "0",
        "size": "35809224",
        "engine": "5",
        "processList": "",
        "unit": "°C",
        "time": 1665509570,
        "value": 18.040000915527,
        "start_time": 1575986560,
        "end_time": 1665509570,
        "interval": 10,
        "npoints": 8952302,
    },
]

FAILURE_MESSAGE = "failure"

YAML_INPUT = {
    CONF_API_KEY: "my_api_key",
    CONF_ID: 1,
    CONF_ONLY_INCLUDE_FEEDID: [6, 7, 8, 9, 10, 18, 27],
    CONF_SCAN_INTERVAL: timedelta(seconds=10),
    CONF_URL: "http://1.1.1.1",
    CONF_VALUE_TEMPLATE: template.Template("{{ value | float + 1500 }}"),
}

IMPORTED_YAML = {
    CONF_API_KEY: "my_api_key",
    CONF_EXCLUDE_FEEDID: None,
    CONF_ID: 1,
    CONF_ONLY_INCLUDE_FEEDID: [6, 7, 8, 9, 10, 18, 27],
    CONF_SENSOR_NAMES: None,
    CONF_SCAN_INTERVAL: 10,
    CONF_UNIT_OF_MEASUREMENT: None,
    CONF_URL: "http://1.1.1.1",
    CONF_VALUE_TEMPLATE: "{{ value | float + 1500 }}",
}

USER_INPUT = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
    CONF_FEED_LIST: ["1"],
    CONF_SCAN_INTERVAL: 10,
}

FINAL = {
    CONF_API_KEY: "my_api_key",
    CONF_EXCLUDE_FEEDID: None,
    CONF_FEED_LIST: ["1"],
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
    CONF_ONLY_INCLUDE_FEEDID: None,
    CONF_SCAN_INTERVAL: 10,
    CONF_VALUE_TEMPLATE: "{{ value | float + 1500 }}",
}

USER_INPUT_2 = {
    CONF_URL: "http://1.1.1.1",
    CONF_API_KEY: "my_api_key",
    CONF_FEED_LIST: ["1", "2"],
    CONF_SCAN_INTERVAL: 30,
}

IMPORTED_YAML_2 = {
    CONF_API_KEY: "my_api_key",
    CONF_EXCLUDE_FEEDID: [2],
    CONF_ID: 1,
    CONF_ONLY_INCLUDE_FEEDID: None,
    CONF_SENSOR_NAMES: None,
    CONF_SCAN_INTERVAL: 10,
    CONF_UNIT_OF_MEASUREMENT: None,
    CONF_URL: "http://1.1.1.1",
    CONF_VALUE_TEMPLATE: None,
}

FINAL_2 = {
    CONF_API_KEY: "my_api_key",
    CONF_EXCLUDE_FEEDID: None,
    CONF_FEED_LIST: ["1", "2"],
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
    CONF_ONLY_INCLUDE_FEEDID: None,
    CONF_SCAN_INTERVAL: 30,
    CONF_VALUE_TEMPLATE: None,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.emoncms.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


PATH = "homeassistant.components.emoncms"
LIB = "EmoncmsClient"


@pytest.fixture
async def emoncms_client() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms success response."""
    with (
        patch(f"{PATH}.config_flow.{LIB}", autospec=True) as mock_client,
        patch(f"{PATH}.sensor.{LIB}", new=mock_client),
    ):
        client = mock_client.return_value
        client.async_request.return_value = {"success": True, "message": FEEDS}
        yield client


@pytest.fixture
async def emoncms_client_failure() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms failure."""
    with patch(f"{PATH}.config_flow.{LIB}", autospec=True) as mock_client:
        client = mock_client.return_value
        client.async_request.return_value = {
            "success": False,
            "message": FAILURE_MESSAGE,
        }
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Mock emoncms config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=IMPORTED_YAML[CONF_ID],
        data=IMPORTED_YAML,
    )


@pytest.fixture
def config_entry_2() -> MockConfigEntry:
    """Mock emoncms config entry with excluded fields."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=IMPORTED_YAML_2[CONF_ID],
        data=IMPORTED_YAML_2,
    )


@pytest.fixture
def config_entry_3() -> MockConfigEntry:
    """Mock emoncms config entry with feed list coming from selector."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=FINAL_2[CONF_ID],
        data=FINAL_2,
    )
