"""Test the integration init functionality."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests import HTTPError
import requests_mock

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.home_connect import SCAN_INTERVAL
from homeassistant.components.home_connect.const import (
    BSH_CHILD_LOCK_STATE,
    BSH_OPERATION_STATE,
    BSH_POWER_STATE,
    BSH_REMOTE_START_ALLOWANCE_STATE,
    COOKING_LIGHTING,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.issue_registry as ir

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

DEPRECATED_KEYS_SERVICE_KV_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "set_option_active",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
            "unit": "",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_option_selected",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
]

SERVICE_KV_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "set_option_active",
        "service_data": {
            "device_id": "DEVICE_ID",
            "custom_options": [
                {
                    "key": "",
                    "value": "",
                    "unit": "",
                },
            ],
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_option_selected",
        "service_data": {
            "device_id": "DEVICE_ID",
            "custom_options": [
                {
                    "key": "",
                    "value": "",
                },
            ],
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "change_setting",
        "service_data": {
            "device_id": "DEVICE_ID",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
    *DEPRECATED_KEYS_SERVICE_KV_CALL_PARAMS,
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


DEPRECATED_KEYS_SERVICE_PROGRAM_CALL_PARAMS = [
    {
        "domain": DOMAIN,
        "service": "select_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": "",
            "key": "",
            "value": "",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "start_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": "",
            "key": "",
            "value": "",
            "unit": "C",
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
            "program": "",
            "custom_options": [
                {
                    "key": "",
                    "value": "",
                },
            ],
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "start_program",
        "service_data": {
            "device_id": "DEVICE_ID",
            "program": "",
            "custom_options": [
                {
                    "key": "",
                    "value": "",
                    "unit": "C",
                }
            ],
        },
        "blocking": True,
    },
    *DEPRECATED_KEYS_SERVICE_PROGRAM_CALL_PARAMS,
]

SERVICE_APPLIANCE_METHOD_MAPPING = {
    "set_option_active": "put",
    "set_option_selected": "put",
    "change_setting": "set_setting",
    "pause_program": "execute_command",
    "resume_program": "execute_command",
    "select_program": "select_program",
    "start_program": "start_program",
}

SERVICE_VALIDATION_ERROR_MAPPING = {
    "set_option_active": r"Error.*set.*program.*options.*",
    "set_option_selected": r"Error.*set.*program.*options.*",
    "change_setting": r"Error.*assign.*value.*setting.*",
    "pause_program": r"Error.*execute.*command.*",
    "resume_program": r"Error.*execute.*command.*",
    "select_program": r"Error.*select.*program.*",
    "start_program": r"Error.*start.*program.*",
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

    service_name = service_call["service"]
    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    assert (
        getattr(appliance, SERVICE_APPLIANCE_METHOD_MAPPING[service_name]).call_count
        == 1
    )


@pytest.mark.parametrize(
    "service_call",
    DEPRECATED_KEYS_SERVICE_KV_CALL_PARAMS
    + DEPRECATED_KEYS_SERVICE_PROGRAM_CALL_PARAMS,
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_service_keys_deprecation(
    service_call: list[dict[str, Any]],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test deprecated service keys."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.haId)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(DOMAIN, "moved_program_options_keys")


@pytest.mark.parametrize(
    ("service_call", "method_called", "expected_args"),
    [
        (
            {
                "domain": DOMAIN,
                "service": "select_program",
                "service_data": {
                    "device_id": "DEVICE_ID",
                    "program": "dishcare_dishwasher_program_eco50",
                    "b_s_h_common_option_start_in_relative": "00:30:00",
                },
            },
            "select_program",
            (
                "Dishcare.Dishwasher.Program.Eco50",
                [{"key": "BSH.Common.Option.StartInRelative", "value": 1800}],
            ),
        ),
        (
            {
                "domain": DOMAIN,
                "service": "start_program",
                "service_data": {
                    "device_id": "DEVICE_ID",
                    "program": "ConsumerProducts.Coffee.Maker.Program.Beverage.Coffee",
                    "consumer_products_coffee_maker_option_bean_amount": "consumer_products_coffee_maker_enum_type_bean_amount_normal",
                },
            },
            "start_program",
            (
                "ConsumerProducts.Coffee.Maker.Program.Beverage.Coffee",
                [
                    {
                        "key": "ConsumerProducts.CoffeeMaker.Option.BeanAmount",
                        "value": "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Normal",
                    }
                ],
            ),
        ),
        (
            {
                "domain": DOMAIN,
                "service": "set_option_active",
                "service_data": {
                    "device_id": "DEVICE_ID",
                    "consumer_products_coffee_maker_option_bean_amount": "consumer_products_coffee_maker_enum_type_bean_amount_normal",
                },
            },
            "put",
            (
                "/programs/active/options",
                {
                    "data": {
                        "options": [
                            {
                                "key": "ConsumerProducts.CoffeeMaker.Option.BeanAmount",
                                "value": "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Normal",
                            },
                        ]
                    },
                },
            ),
        ),
        (
            {
                "domain": DOMAIN,
                "service": "set_option_selected",
                "service_data": {
                    "device_id": "DEVICE_ID",
                    "consumer_products_coffee_maker_option_bean_amount": "consumer_products_coffee_maker_enum_type_bean_amount_normal",
                },
            },
            "put",
            (
                "/programs/selected/options",
                {
                    "data": {
                        "options": [
                            {
                                "key": "ConsumerProducts.CoffeeMaker.Option.BeanAmount",
                                "value": "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Normal",
                            }
                        ],
                    },
                },
            ),
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_recognized_options(
    hass: HomeAssistant,
    service_call: list[dict[str, Any]],
    method_called: str,
    expected_args: str,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Test recognized options."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.haId)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    method_mock: MagicMock = getattr(appliance, method_called)
    assert method_mock.call_count == 1
    assert method_mock.call_args[0] == expected_args


@pytest.mark.usefixtures("bypass_throttle")
async def test_services_exception_device_id(
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

    service_call["service_data"]["device_id"] = "DOES_NOT_EXISTS"

    with pytest.raises(ValueError):
        await hass.services.async_call(**service_call)


@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_services_exception(
    service_call: list[dict[str, Any]],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    problematic_appliance: Mock,
) -> None:
    """Raise a ValueError when device id does not match."""
    get_appliances.return_value = [problematic_appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, problematic_appliance.haId)},
    )

    service_call["service_data"]["device_id"] = device_entry.id

    service_name = service_call["service"]
    with pytest.raises(
        ServiceValidationError,
        match=SERVICE_VALIDATION_ERROR_MAPPING[service_name],
    ):
        await hass.services.async_call(**service_call)


async def test_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_v1_1: MockConfigEntry,
    appliance: Mock,
    platforms: list[Platform],
) -> None:
    """Test entity migration."""

    config_entry_v1_1.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_v1_1.entry_id,
        identifiers={(DOMAIN, appliance.haId)},
    )

    test_entities = [
        (
            SENSOR_DOMAIN,
            "Operation State",
            BSH_OPERATION_STATE,
        ),
        (
            SWITCH_DOMAIN,
            "ChildLock",
            BSH_CHILD_LOCK_STATE,
        ),
        (
            SWITCH_DOMAIN,
            "Power",
            BSH_POWER_STATE,
        ),
        (
            BINARY_SENSOR_DOMAIN,
            "Remote Start",
            BSH_REMOTE_START_ALLOWANCE_STATE,
        ),
        (
            LIGHT_DOMAIN,
            "Light",
            COOKING_LIGHTING,
        ),
    ]

    for domain, old_unique_id_suffix, _ in test_entities:
        entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            f"{appliance.haId}-{old_unique_id_suffix}",
            device_id=device_entry.id,
            config_entry=config_entry_v1_1,
        )

    with patch("homeassistant.components.home_connect.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry_v1_1.entry_id)
        await hass.async_block_till_done()

    for domain, _, expected_unique_id_suffix in test_entities:
        assert entity_registry.async_get_entity_id(
            domain, DOMAIN, f"{appliance.haId}-{expected_unique_id_suffix}"
        )
    assert config_entry_v1_1.minor_version == 2
