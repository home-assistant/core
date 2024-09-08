"""Test the integration init functionality."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests import HTTPError
import requests_mock

from homeassistant.components.home_connect import SCAN_INTERVAL
from homeassistant.components.home_connect.const import (
    ATTR_KEY,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    DOMAIN,
    OAUTH2_TOKEN,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    FAKE_ACCESS_TOKEN,
    FAKE_REFRESH_TOKEN,
    SERVER_ACCESS_TOKEN,
    get_all_appliances,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SERVICE_KV_CALL_PARAMS = [
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_OPTION_ACTIVE,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
            ATTR_KEY: "",
            ATTR_VALUE: "",
            ATTR_UNIT: "",
        },
        "blocking": True,
    },
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_OPTION_SELECTED,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
            ATTR_KEY: "",
            ATTR_VALUE: "",
        },
        "blocking": True,
    },
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_SETTING,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
            ATTR_KEY: "",
            ATTR_VALUE: "",
        },
        "blocking": True,
    },
]

SERVICE_COMMAND_CALL_PARAMS = [
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_PAUSE_PROGRAM,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
        },
        "blocking": True,
    },
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_RESUME_PROGRAM,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
        },
        "blocking": True,
    },
]


SERVICE_PROGRAM_CALL_PARAMS = [
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_SELECT_PROGRAM,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
            ATTR_PROGRAM: "",
            ATTR_KEY: "",
            ATTR_VALUE: "",
        },
        "blocking": True,
    },
    {
        ATTR_DOMAIN: DOMAIN,
        ATTR_SERVICE: SERVICE_START_PROGRAM,
        ATTR_SERVICE_DATA: {
            ATTR_DEVICE_ID: "DEVICE_ID",
            ATTR_PROGRAM: "",
            ATTR_KEY: "",
            ATTR_VALUE: "",
            ATTR_UNIT: "C",
        },
        "blocking": True,
    },
]

SERVICE_APPLIANCE_METHOD_MAPPING = {
    SERVICE_OPTION_ACTIVE: "set_options_active_program",
    SERVICE_OPTION_SELECTED: "set_options_selected_program",
    SERVICE_SETTING: "set_setting",
    SERVICE_PAUSE_PROGRAM: "execute_command",
    SERVICE_RESUME_PROGRAM: "execute_command",
    SERVICE_SELECT_PROGRAM: "select_program",
    SERVICE_START_PROGRAM: "start_program",
}


@pytest.mark.usefixtures("bypass_throttle")
async def test_api_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test setup and unload."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_update_throttle(
    appliance: Mock,
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test to check Throttle functionality."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    get_appliances_call_count = get_appliances.call_count

    # First re-load after 1 minute is not blocked.
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    freezer.tick(SCAN_INTERVAL.seconds + 0.1)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert get_appliances.call_count == get_appliances_call_count + 1

    # Second re-load is blocked by Throttle.
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    freezer.tick(SCAN_INTERVAL.seconds - 0.1)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert get_appliances.call_count == get_appliances_call_count + 1


@pytest.mark.usefixtures("bypass_throttle")
async def test_exception_handling(
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    get_appliances: MagicMock,
    problematic_appliance: Mock,
) -> None:
    """Test exception handling."""
    get_appliances.return_value = [problematic_appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize("token_expiration_time", [12345])
@pytest.mark.usefixtures("bypass_throttle")
async def test_token_refresh_success(
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    requests_mock: requests_mock.Mocker,
    setup_credentials: None,
) -> None:
    """Test where token is expired and the refresh attempt succeeds."""

    assert config_entry.data["token"]["access_token"] == FAKE_ACCESS_TOKEN

    requests_mock.post(OAUTH2_TOKEN, json=SERVER_ACCESS_TOKEN)
    requests_mock.get("/api/homeappliances", json={"data": {"homeappliances": []}})

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Verify token request
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": FAKE_REFRESH_TOKEN,
    }

    # Verify updated token
    assert (
        config_entry.data["token"]["access_token"]
        == SERVER_ACCESS_TOKEN["access_token"]
    )


@pytest.mark.usefixtures("bypass_throttle")
async def test_http_error(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test HTTP errors during setup integration."""
    get_appliances.side_effect = HTTPError(response=MagicMock())
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    assert get_appliances.call_count == 1


@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_services(
    service_call: list[dict[str, Any]],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Create and test services."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.haId)},
    )

    service_name = service_call[ATTR_SERVICE]
    service_call[ATTR_SERVICE_DATA]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    assert (
        getattr(appliance, SERVICE_APPLIANCE_METHOD_MAPPING[service_name]).call_count
        == 1
    )


@pytest.mark.usefixtures("bypass_throttle")
async def test_services_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Raise a ValueError when device id does not match."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    service_call = SERVICE_KV_CALL_PARAMS[0]

    service_call[ATTR_SERVICE_DATA]["device_id"] = "DOES_NOT_EXISTS"

    with pytest.raises(ValueError):
        await hass.services.async_call(**service_call)
