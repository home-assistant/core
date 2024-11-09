"""Define test fixtures for SimpliSafe."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simplipy.system.v3 import SystemV3

from homeassistant.components.simplisafe.const import DOMAIN
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from .common import REFRESH_TOKEN, USER_ID, USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture

CODE = "12345"
PASSWORD = "password"
SYSTEM_ID = 12345


@pytest.fixture(name="api")
def api_fixture(
    data_subscription: JsonObjectType, system_v3: SystemV3, websocket: Mock
) -> Mock:
    """Define a simplisafe-python API object."""
    return Mock(
        async_get_systems=AsyncMock(return_value={SYSTEM_ID: system_v3}),
        refresh_token=REFRESH_TOKEN,
        subscription_data=data_subscription,
        user_id=USER_ID,
        websocket=websocket,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, str], unique_id: str
) -> MockConfigEntry:
    """Define a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=unique_id, data=config, options={CONF_CODE: "1234"}
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, str]:
    """Define config entry data config."""
    return {
        CONF_TOKEN: REFRESH_TOKEN,
        CONF_USERNAME: USERNAME,
    }


@pytest.fixture(name="credentials_config")
def credentials_config_fixture() -> dict[str, str]:
    """Define a username/password config."""
    return {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }


@pytest.fixture(name="data_latest_event", scope="package")
def data_latest_event_fixture() -> JsonObjectType:
    """Define latest event data."""
    return load_json_object_fixture("latest_event_data.json", "simplisafe")


@pytest.fixture(name="data_sensor", scope="package")
def data_sensor_fixture() -> JsonObjectType:
    """Define sensor data."""
    return load_json_object_fixture("sensor_data.json", "simplisafe")


@pytest.fixture(name="data_settings", scope="package")
def data_settings_fixture() -> JsonObjectType:
    """Define settings data."""
    return load_json_object_fixture("settings_data.json", "simplisafe")


@pytest.fixture(name="data_subscription", scope="package")
def data_subscription_fixture() -> JsonObjectType:
    """Define subscription data."""
    data = load_json_object_fixture("subscription_data.json", "simplisafe")
    return {SYSTEM_ID: data}


@pytest.fixture(name="reauth_config")
def reauth_config_fixture() -> dict[str, str]:
    """Define a reauth config."""
    return {
        CONF_PASSWORD: PASSWORD,
    }


@pytest.fixture(name="setup_simplisafe")
async def setup_simplisafe_fixture(
    hass: HomeAssistant, api: Mock, config: dict[str, str]
) -> AsyncGenerator[None]:
    """Define a fixture to set up SimpliSafe."""
    with (
        patch(
            "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.API.async_from_auth",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.API.async_from_refresh_token",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.SimpliSafe._async_start_websocket_loop"
        ),
        patch(
            "homeassistant.components.simplisafe.PLATFORMS",
            [],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="sms_config")
def sms_config_fixture() -> dict[str, str]:
    """Define a SMS-based two-factor authentication config."""
    return {
        CONF_CODE: CODE,
    }


@pytest.fixture(name="system_v3")
def system_v3_fixture(
    data_latest_event: JsonObjectType,
    data_sensor: JsonObjectType,
    data_settings: JsonObjectType,
    data_subscription: JsonObjectType,
) -> SystemV3:
    """Define a simplisafe-python V3 System object."""
    system = SystemV3(Mock(subscription_data=data_subscription), SYSTEM_ID)
    system.async_get_latest_event = AsyncMock(return_value=data_latest_event)
    system.sensor_data = data_sensor
    system.settings_data = data_settings
    system.generate_device_objects()
    return system


@pytest.fixture(name="unique_id")
def unique_id_fixture() -> str:
    """Define a unique ID."""
    return USER_ID


@pytest.fixture(name="websocket")
def websocket_fixture() -> Mock:
    """Define a simplisafe-python websocket object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_listen=AsyncMock(),
    )
