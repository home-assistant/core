"""Define test fixtures for SimpliSafe."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simplipy.system.v3 import SystemV3

from homeassistant.components.simplisafe import SimpliSafe
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


@pytest.fixture(name="patch_simplisafe_api")
def patch_simplisafe_api_fixture(api: Mock, websocket: Mock):
    """Patch the SimpliSafe API creation methods and websocket loop."""
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
    ):
        # Patch the websocket on the api object
        api.websocket = websocket
        yield


@pytest.fixture(name="setup_simplisafe")
async def setup_simplisafe_fixture(
    hass: HomeAssistant, api: Mock, config: dict[str, str], patch_simplisafe_api
) -> None:
    """Define a fixture to set up SimpliSafe for config flow tests."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


@pytest.fixture
async def simplisafe_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    monkeypatch: pytest.MonkeyPatch,
) -> SimpliSafe:
    """Capture the real SimpliSafe manager created by HA setup."""

    manager = None  # outer variable to capture the instance
    orig_init = SimpliSafe.__init__

    def capture_init(self, *args, **kwargs):
        nonlocal manager
        orig_init(self, *args, **kwargs)  # call the original __init__
        manager = self  # capture the instance for the fixture

    # Apply monkeypatch just to capture the manager
    monkeypatch.setattr(
        "homeassistant.components.simplisafe.SimpliSafe.__init__",
        capture_init,
    )

    # Let HA set up the integration normally
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert manager is not None
    return manager


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


async def never_return() -> None:
    """Never returning task to simulate waiting on websocket listen."""
    while True:
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            return


@pytest.fixture(name="websocket")
def websocket_fixture() -> Mock:
    """Define a simplisafe-python websocket object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_listen=never_return,
    )
