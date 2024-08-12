"""GeniusHub tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.geniushub.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.components.smhi.common import AsyncMock
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.geniushub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_geniushub_client() -> Generator[AsyncMock]:
    """Mock a GeniusHub client."""
    with patch(
        "homeassistant.components.geniushub.config_flow.GeniusService",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.request.return_value = {
            "data": {
                "UID": "aa:bb:cc:dd:ee:ff",
            }
        }
        yield client


@pytest.fixture
def mock_local_config_entry() -> MockConfigEntry:
    """Mock a local config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="aa:bb:cc:dd:ee:ff",
        data={
            CONF_HOST: "10.0.0.131",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_cloud_config_entry() -> MockConfigEntry:
    """Mock a cloud config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Genius hub",
        data={
            CONF_TOKEN: "abcdef",
        },
    )


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("zones_test_data.json", DOMAIN)
    devices = load_json_object_fixture("devices_test_data.json", DOMAIN)
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/auth/release",
        json=({"data": {"UID": "aa:bb:cc:dd:ee:ff", "release": "10.0"}}),
    )
    aioclient_mock.get("http://10.0.0.130:1223/v3/zones", json=zones)
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/data_manager",
        json=devices,
    )


@pytest.fixture(autouse=True)
def mock_single_zone_with_switch(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("single_zone_test_data.json", DOMAIN)
    devices = load_json_object_fixture("single_switch_test_data.json", DOMAIN)
    switch_on = load_json_object_fixture("switch_on_test_data.json", DOMAIN)
    switch_off = load_json_object_fixture("switch_off_test_data.json", DOMAIN)
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/auth/release",
        json=({"data": {"UID": "aa:bb:cc:dd:ee:ff", "release": "10.0"}}),
    )
    aioclient_mock.get("http://10.0.0.130:1223/v3/zones", json=zones)
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/data_manager",
        json=devices,
    )
    aioclient_mock.patch(
        "http://10.0.0.130:1223/v3/zone/32",
        json=switch_on,
    )
    aioclient_mock.patch(
        "http://10.0.0.131:1223/v3/zone/32",
        json=switch_off,
    )
