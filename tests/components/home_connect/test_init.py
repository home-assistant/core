"""Test the integration init functionality."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, patch

from aiohomeconnect.const import OAUTH2_TOKEN
from aiohomeconnect.model import OptionKey, ProgramKey, SettingKey, StatusKey
from aiohomeconnect.model.error import HomeConnectError
import pytest
import requests_mock
import respx

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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

SERVICE_KV_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "set_option_active",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": OptionKey.BSH_COMMON_FINISH_IN_RELATIVE.value,
            "value": 43200,
            "unit": "seconds",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_option_selected",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE.value,
            "value": "LaundryCare.Washer.EnumType.Temperature.GC40",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "change_setting",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": SettingKey.BSH_COMMON_CHILD_LOCK.value,
            "value": True,
        },
        "blocking": True,
    },
]

SERVICE_COMMAND_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "pause_program",
        "service_data": {
            "device_id": "DEVICE_ID",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "resume_program",
        "service_data": {
            "device_id": "DEVICE_ID",
        },
        "blocking": True,
    },
]


SERVICE_PROGRAM_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "select_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": ProgramKey.LAUNDRY_CARE_WASHER_COTTON.value,
            "key": OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE.value,
            "value": "LaundryCare.Washer.EnumType.Temperature.GC40",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "start_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": ProgramKey.LAUNDRY_CARE_WASHER_COTTON.value,
            "key": OptionKey.BSH_COMMON_FINISH_IN_RELATIVE.value,
            "value": 43200,
            "unit": "seconds",
        },
        "blocking": True,
    },
]

SERVICE_APPLIANCE_METHOD_MAPPING = {
    "set_option_active": "set_active_program_option",
    "set_option_selected": "set_selected_program_option",
    "change_setting": "set_setting",
    "pause_program": "put_command",
    "resume_program": "put_command",
    "select_program": "set_selected_program",
    "start_program": "start_program",
}


async def test_entry_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test setup and unload."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_exception_handling(
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test exception handling."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize("token_expiration_time", [12345])
@respx.mock
async def test_token_refresh_success(
    hass: HomeAssistant,
    platforms: list[Platform],
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    requests_mock: requests_mock.Mocker,
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test where token is expired and the refresh attempt succeeds."""

    assert config_entry.data["token"]["access_token"] == FAKE_ACCESS_TOKEN

    requests_mock.post(OAUTH2_TOKEN, json=SERVER_ACCESS_TOKEN)
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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    with (
        patch("homeassistant.components.home_connect.PLATFORMS", platforms),
        patch("homeassistant.components.home_connect.HomeConnectClient") as client_mock,
    ):
        client_mock.side_effect = MagicMock(side_effect=init_side_effect)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
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


async def test_client_error(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test client errors during setup integration."""
    client_with_exception.get_home_appliances.return_value = None
    client_with_exception.get_home_appliances.side_effect = HomeConnectError()
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert not await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
    assert client_with_exception.get_home_appliances.call_count == 1


@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
async def test_services(
    service_call: dict[str, Any],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Create and test services."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance_ha_id)},
    )

    service_name = service_call["service"]
    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    assert (
        getattr(client, SERVICE_APPLIANCE_METHOD_MAPPING[service_name]).call_count == 1
    )


@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
async def test_services_exception(
    service_call: dict[str, Any],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
    appliance_ha_id: str,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Raise a HomeAssistantError when there is an API error."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance_ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(**service_call)


async def test_services_appliance_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Raise a ServiceValidationError when device id does not match."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    service_call = SERVICE_KV_CALL_PARAMS[0]

    service_call["service_data"]["device_id"] = "DOES_NOT_EXISTS"

    with pytest.raises(ServiceValidationError, match=r"Device entry.*not found"):
        await hass.services.async_call(**service_call)

    unrelated_config_entry = MockConfigEntry(
        domain="TEST",
    )
    unrelated_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=unrelated_config_entry.entry_id,
        identifiers={("RANDOM", "ABCD")},
    )
    service_call["service_data"]["device_id"] = device_entry.id

    with pytest.raises(
        ServiceValidationError, match=r"Home Connect config entry.*not found"
    ):
        await hass.services.async_call(**service_call)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("RANDOM", "ABCD")},
    )
    service_call["service_data"]["device_id"] = device_entry.id

    with pytest.raises(ServiceValidationError, match=r"Appliance.*not found"):
        await hass.services.async_call(**service_call)


async def test_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_v1_1: MockConfigEntry,
    appliance_ha_id: str,
    platforms: list[Platform],
) -> None:
    """Test entity migration."""

    config_entry_v1_1.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_v1_1.entry_id,
        identifiers={(DOMAIN, appliance_ha_id)},
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
            f"{appliance_ha_id}-{old_unique_id_suffix}",
            device_id=device_entry.id,
            config_entry=config_entry_v1_1,
        )

    with patch("homeassistant.components.home_connect.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry_v1_1.entry_id)
        await hass.async_block_till_done()

    for domain, _, expected_unique_id_suffix in test_entities:
        assert entity_registry.async_get_entity_id(
            domain, DOMAIN, f"{appliance_ha_id}-{expected_unique_id_suffix}"
        )
    assert config_entry_v1_1.minor_version == 2


async def test_bsh_key_transformations() -> None:
    """Test that the key transformations are compatible valid translations keys and can be reversed."""
    program = "Dishcare.Dishwasher.Program.Eco50"
    translation_key = bsh_key_to_translation_key(program)
    assert RE_TRANSLATION_KEY.match(translation_key)
