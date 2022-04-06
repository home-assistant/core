"""Define test fixtures for SimpliSafe."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simplipy.system.v3 import SystemV3

from homeassistant.components.simplisafe.config_flow import CONF_AUTH_CODE
from homeassistant.components.simplisafe.const import CONF_USER_ID, DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

REFRESH_TOKEN = "token123"
SYSTEM_ID = "system_123"
USER_ID = "12345"


@pytest.fixture(name="api")
def api_fixture(data_subscription, system_v3, websocket):
    """Define a fixture for a simplisafe-python API object."""
    return Mock(
        async_get_systems=AsyncMock(return_value={SYSTEM_ID: system_v3}),
        refresh_token=REFRESH_TOKEN,
        subscription_data=data_subscription,
        user_id=USER_ID,
        websocket=websocket,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=USER_ID, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_USER_ID: USER_ID,
        CONF_TOKEN: REFRESH_TOKEN,
    }


@pytest.fixture(name="config_code")
def config_code_fixture(hass):
    """Define a authorization code."""
    return {
        CONF_AUTH_CODE: "code123",
    }


@pytest.fixture(name="data_latest_event", scope="session")
def data_latest_event_fixture():
    """Define latest event data."""
    return json.loads(load_fixture("latest_event_data.json", "simplisafe"))


@pytest.fixture(name="data_sensor", scope="session")
def data_sensor_fixture():
    """Define sensor data."""
    return json.loads(load_fixture("sensor_data.json", "simplisafe"))


@pytest.fixture(name="data_settings", scope="session")
def data_settings_fixture():
    """Define settings data."""
    return json.loads(load_fixture("settings_data.json", "simplisafe"))


@pytest.fixture(name="data_subscription", scope="session")
def data_subscription_fixture():
    """Define subscription data."""
    return json.loads(load_fixture("subscription_data.json", "simplisafe"))


@pytest.fixture(name="setup_simplisafe")
async def setup_simplisafe_fixture(hass, api, config):
    """Define a fixture to set up SimpliSafe."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        return_value=api,
    ), patch(
        "homeassistant.components.simplisafe.API.async_from_auth", return_value=api
    ), patch(
        "homeassistant.components.simplisafe.API.async_from_refresh_token",
        return_value=api,
    ), patch(
        "homeassistant.components.simplisafe.SimpliSafe._async_start_websocket_loop"
    ), patch(
        "homeassistant.components.simplisafe.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="system_v3")
def system_v3_fixture(data_latest_event, data_sensor, data_settings, data_subscription):
    """Define a fixture for a simplisafe-python V3 System object."""
    system = SystemV3(Mock(subscription_data=data_subscription), SYSTEM_ID)
    system.async_get_latest_event = AsyncMock(return_value=data_latest_event)
    system.sensor_data = data_sensor
    system.settings_data = data_settings
    system.generate_device_objects()
    return system


@pytest.fixture(name="websocket")
def websocket_fixture():
    """Define a fixture for a simplisafe-python websocket object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_listen=AsyncMock(),
    )
