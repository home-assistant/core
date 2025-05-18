"""Test the integration init functionality."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.const import OAUTH2_TOKEN
from aiohomeconnect.model import HomeAppliance, SettingKey, StatusKey
from aiohomeconnect.model.error import (
    HomeConnectError,
    TooManyRequestsError,
    UnauthorizedError,
)
import aiohttp
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from script.hassfest.translations import RE_TRANSLATION_KEY

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    FAKE_ACCESS_TOKEN,
    FAKE_REFRESH_TOKEN,
    SERVER_ACCESS_TOKEN,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_entry_setup(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test setup and unload."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("token_expiration_time", [12345])
async def test_token_refresh_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    client: MagicMock,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test where token is expired and the refresh attempt succeeds."""

    assert config_entry.data["token"]["access_token"] == FAKE_ACCESS_TOKEN

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )
    appliances = client.get_home_appliances.return_value

    async def mock_get_home_appliances():
        await client._auth.async_get_access_token()
        return appliances

    client.get_home_appliances.return_value = None
    client.get_home_appliances.side_effect = mock_get_home_appliances

    def init_side_effect(auth) -> MagicMock:
        client._auth = auth
        return client

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with (
        patch("homeassistant.components.home_connect.PLATFORMS", platforms),
        patch("homeassistant.components.home_connect.HomeConnectClient") as client_mock,
    ):
        client_mock.side_effect = MagicMock(side_effect=init_side_effect)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

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


@pytest.mark.parametrize("token_expiration_time", [12345])
@pytest.mark.parametrize(
    ("aioclient_mock_args", "expected_config_entry_state"),
    [
        (
            {
                "status": 400,
                "json": {"error": "invalid_grant"},
            },
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            {
                "status": 500,
            },
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            {
                "exc": aiohttp.ClientError,
            },
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_token_refresh_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    aioclient_mock_args: dict[str, Any],
    expected_config_entry_state: ConfigEntryState,
) -> None:
    """Test where token is expired and the refresh attempt fails."""

    config_entry.data["token"]["access_token"] = FAKE_ACCESS_TOKEN

    aioclient_mock.post(
        OAUTH2_TOKEN,
        **aioclient_mock_args,
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with patch(
        "homeassistant.components.home_connect.HomeConnectClient", return_value=client
    ):
        assert not await integration_setup(client)
        await hass.async_block_till_done()

    assert config_entry.state == expected_config_entry_state


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (HomeConnectError(), ConfigEntryState.SETUP_RETRY),
        (UnauthorizedError("error.key"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_client_error(
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    exception: HomeConnectError,
    expected_state: ConfigEntryState,
) -> None:
    """Test client errors during setup integration."""
    client_with_exception.get_home_appliances.return_value = None
    client_with_exception.get_home_appliances.side_effect = exception
    assert not await integration_setup(client_with_exception)
    assert config_entry.state == expected_state
    assert client_with_exception.get_home_appliances.call_count == 1


@pytest.mark.parametrize(
    "raising_exception_method",
    [
        "get_settings",
        "get_status",
        "get_all_programs",
        "get_available_commands",
        "get_available_program",
    ],
)
async def test_client_rate_limit_error(
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    raising_exception_method: str,
) -> None:
    """Test client errors during setup integration."""
    retry_after = 42

    original_mock = getattr(client, raising_exception_method)
    mock = AsyncMock()

    async def side_effect(*args, **kwargs):
        if mock.call_count <= 1:
            raise TooManyRequestsError("error.key", retry_after=retry_after)
        return await original_mock(*args, **kwargs)

    mock.side_effect = side_effect
    setattr(client, raising_exception_method, mock)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with patch(
        "homeassistant.components.home_connect.coordinator.asyncio_sleep",
    ) as asyncio_sleep_mock:
        assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert mock.call_count >= 2
    asyncio_sleep_mock.assert_called_once_with(retry_after)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_required_program_or_at_least_an_option(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    "Test that the set_program_and_options does raise an exception if no program nor options are set."

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    with pytest.raises(
        ServiceValidationError,
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_program_and_options",
            {
                "device_id": device_entry.id,
                "affects_to": "selected_program",
            },
            True,
        )


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_v1_1: MockConfigEntry,
    platforms: list[Platform],
    appliance: HomeAppliance,
) -> None:
    """Test entity migration."""

    config_entry_v1_1.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_v1_1.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    test_entities = [
        (
            SENSOR_DOMAIN,
            "Operation State",
            StatusKey.BSH_COMMON_OPERATION_STATE,
        ),
        (
            SWITCH_DOMAIN,
            "ChildLock",
            SettingKey.BSH_COMMON_CHILD_LOCK,
        ),
        (
            SWITCH_DOMAIN,
            "Power",
            SettingKey.BSH_COMMON_POWER_STATE,
        ),
        (
            BINARY_SENSOR_DOMAIN,
            "Remote Start",
            StatusKey.BSH_COMMON_REMOTE_CONTROL_START_ALLOWED,
        ),
        (
            LIGHT_DOMAIN,
            "Light",
            SettingKey.COOKING_COMMON_LIGHTING,
        ),
        (  # An already migrated entity
            SWITCH_DOMAIN,
            SettingKey.REFRIGERATION_COMMON_VACATION_MODE,
            SettingKey.REFRIGERATION_COMMON_VACATION_MODE,
        ),
    ]

    for domain, old_unique_id_suffix, _ in test_entities:
        entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            f"{appliance.ha_id}-{old_unique_id_suffix}",
            device_id=device_entry.id,
            config_entry=config_entry_v1_1,
        )

    with patch("homeassistant.components.home_connect.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry_v1_1.entry_id)
        await hass.async_block_till_done()

    for domain, _, expected_unique_id_suffix in test_entities:
        assert entity_registry.async_get_entity_id(
            domain, DOMAIN, f"{appliance.ha_id}-{expected_unique_id_suffix}"
        )
    assert config_entry_v1_1.minor_version == 2


async def test_bsh_key_transformations() -> None:
    """Test that the key transformations are compatible valid translations keys and can be reversed."""
    program = "Dishcare.Dishwasher.Program.Eco50"
    translation_key = bsh_key_to_translation_key(program)
    assert RE_TRANSLATION_KEY.match(translation_key)


async def test_config_entry_unique_id_migration(
    hass: HomeAssistant,
    config_entry_v1_2: MockConfigEntry,
) -> None:
    """Test that old config entries use the unique id obtained from the JWT subject."""
    config_entry_v1_2.add_to_hass(hass)

    assert config_entry_v1_2.unique_id != "1234567890"
    assert config_entry_v1_2.minor_version == 2

    await hass.config_entries.async_setup(config_entry_v1_2.entry_id)
    await hass.async_block_till_done()

    assert config_entry_v1_2.unique_id == "1234567890"
    assert config_entry_v1_2.minor_version == 3
