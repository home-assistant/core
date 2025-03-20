"""Fixtures for emoncms integration tests."""

from collections.abc import AsyncGenerator, Generator
import copy
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.emoncms.const import CONF_ONLY_INCLUDE_FEEDID, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_PLATFORM,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry

UNITS = ["kWh", "Wh", "W", "V", "A", "VA", "°C", "°F", "K", "Hz", "hPa", ""]


def get_feed(
    number: int, unit: str = "W", value: int = 18.04, timestamp: int = 1665509570
):
    """Generate feed details."""
    return {
        "id": str(number),
        "userid": "1",
        "name": f"parameter {number}",
        "tag": "tag",
        "size": "35809224",
        "unit": unit,
        "time": timestamp,
        "value": value,
    }


FEEDS = [get_feed(i + 1, unit=unit) for i, unit in enumerate(UNITS)]


EMONCMS_FAILURE = {"success": False, "message": "failure"}

FLOW_RESULT = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: [str(i + 1) for i in range(len(UNITS))],
    CONF_URL: "http://1.1.1.1",
}

SENSOR_NAME = "emoncms@1.1.1.1"

YAML_BASE = {
    CONF_PLATFORM: "emoncms",
    CONF_API_KEY: "my_api_key",
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
}

YAML = {
    **YAML_BASE,
    CONF_ONLY_INCLUDE_FEEDID: [1],
}


@pytest.fixture
def emoncms_yaml_config() -> ConfigType:
    """Mock emoncms yaml configuration."""
    return {"sensor": YAML}


@pytest.fixture
def emoncms_yaml_config_with_template() -> ConfigType:
    """Mock emoncms yaml conf with template parameter."""
    return {"sensor": {**YAML, CONF_VALUE_TEMPLATE: "{{ value | float + 1500 }}"}}


@pytest.fixture
def emoncms_yaml_config_no_include_only_feed_id() -> ConfigType:
    """Mock emoncms yaml configuration without include_only_feed_id parameter."""
    return {"sensor": YAML_BASE}


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Mock emoncms config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT,
    )


FLOW_RESULT_SECOND_URL = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_SECOND_URL[CONF_URL] = "http://1.1.1.2"


@pytest.fixture
def config_entry_unique_id() -> MockConfigEntry:
    """Mock emoncms config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT_SECOND_URL,
        unique_id="123-53535292",
    )


FLOW_RESULT_NO_FEED = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_NO_FEED[CONF_ONLY_INCLUDE_FEEDID] = None


@pytest.fixture
def config_no_feed() -> MockConfigEntry:
    """Mock emoncms config entry with no feed selected."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT_NO_FEED,
    )


FLOW_RESULT_SINGLE_FEED = copy.deepcopy(FLOW_RESULT)
FLOW_RESULT_SINGLE_FEED[CONF_ONLY_INCLUDE_FEEDID] = ["1"]


@pytest.fixture
def config_single_feed() -> MockConfigEntry:
    """Mock emoncms config entry with a single feed exposed."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT_SINGLE_FEED,
        entry_id="XXXXXXXX",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.emoncms.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def emoncms_client() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms success response."""
    with (
        patch(
            "homeassistant.components.emoncms.EmoncmsClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.emoncms.config_flow.EmoncmsClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_request.return_value = {"success": True, "message": FEEDS}
        client.async_get_uuid.return_value = "123-53535292"
        yield client
