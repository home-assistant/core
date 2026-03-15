"""Tests for the Home Connect actions."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    HomeAppliance,
    Option,
    OptionKey,
    Program,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectError, NoProgramActiveError
import pytest
from syrupy.assertion import SnapshotAssertion
from voluptuous.error import MultipleInvalid

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

SERVICE_KV_CALL_PARAMS = [
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


SERVICE_APPLIANCE_METHOD_MAPPING = {
    "change_setting": "set_setting",
}

SERVICE_VALIDATION_ERROR_MAPPING = {
    "change_setting": r"Error.*assigning.*value.*setting.*",
}


SERVICES_SET_PROGRAM_AND_OPTIONS = [
    {
        "domain": DOMAIN,
        "service": "set_program_and_options",
        "service_data": {
            "device_id": "DEVICE_ID",
            "affects_to": "selected_program",
            "program": "dishcare_dishwasher_program_eco_50",
            "b_s_h_common_option_start_in_relative": 1800,
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_program_and_options",
        "service_data": {
            "device_id": "DEVICE_ID",
            "affects_to": "active_program",
            "program": "consumer_products_coffee_maker_program_beverage_coffee",
            "consumer_products_coffee_maker_option_bean_amount": "consumer_products_coffee_maker_enum_type_bean_amount_normal",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_program_and_options",
        "service_data": {
            "device_id": "DEVICE_ID",
            "affects_to": "active_program",
            "consumer_products_coffee_maker_option_coffee_milk_ratio": "consumer_products_coffee_maker_enum_type_coffee_milk_ratio_50_percent",
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_program_and_options",
        "service_data": {
            "device_id": "DEVICE_ID",
            "affects_to": "selected_program",
            "consumer_products_coffee_maker_option_fill_quantity": 35,
        },
        "blocking": True,
    },
]


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize("service_call", SERVICE_KV_CALL_PARAMS)
async def test_key_value_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service_call: dict[str, Any],
) -> None:
    """Create and test services."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_name = service_call["service"]
    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    assert (
        getattr(client, SERVICE_APPLIANCE_METHOD_MAPPING[service_name]).call_count == 1
    )


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    ("service_call", "called_method"),
    zip(
        SERVICES_SET_PROGRAM_AND_OPTIONS,
        [
            "set_selected_program",
            "start_program",
            "set_active_program_options",
            "set_selected_program_options",
        ],
        strict=True,
    ),
)
async def test_set_program_and_options(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service_call: dict[str, Any],
    called_method: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test recognized options."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()
    method_mock: MagicMock = getattr(client, called_method)
    assert method_mock.call_count == 1
    assert method_mock.call_args == snapshot


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    ("service_call", "error_regex"),
    zip(
        SERVICES_SET_PROGRAM_AND_OPTIONS,
        [
            r"Error.*selecting.*program.*",
            r"Error.*starting.*program.*",
            r"Error.*setting.*options.*active.*program.*",
            r"Error.*setting.*options.*selected.*program.*",
        ],
        strict=True,
    ),
)
async def test_set_program_and_options_exceptions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service_call: dict[str, Any],
    error_regex: str,
) -> None:
    """Test recognized options."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    with pytest.raises(HomeAssistantError, match=error_regex):
        await hass.services.async_call(**service_call)


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    "additional_service_data",
    [
        {},
        {
            "b_s_h_common_option_start_in_relative": 1200,
            "b_s_h_common_option_finish_in_relative": 1200,
        },
        {
            "b_s_h_common_option_start_in_relative": 1200,
        },
        {
            "b_s_h_common_option_finish_in_relative": 1200,
        },
    ],
)
@pytest.mark.parametrize(
    "options_already_set",
    [
        None,
        [
            Option(
                key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
                value=True,
            )
        ],
    ],
)
@pytest.mark.parametrize(
    ("get_active_program_side_effect", "get_selected_program_call_count"),
    [(None, 0), (NoProgramActiveError("error.key"), 1)],
)
async def test_start_selected_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    additional_service_data: dict[str, Any],
    options_already_set: list[Option] | None,
    get_active_program_side_effect: NoProgramActiveError | None,
    get_selected_program_call_count: int,
    snapshot: SnapshotAssertion,
) -> None:
    """Test starting the selected program with optional parameter overrides."""
    client.get_active_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=options_already_set,
        ),
        side_effect=get_active_program_side_effect,
    )
    client.get_selected_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=options_already_set,
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    await hass.services.async_call(
        domain=DOMAIN,
        service="start_selected_program",
        service_data={
            "device_id": device_entry.id,
            **additional_service_data,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    client.get_active_program.assert_awaited_once_with(appliance.ha_id)
    assert client.get_selected_program.call_count == get_selected_program_call_count
    for call_args in client.start_program.call_args_list:
        assert call_args[0][0] == appliance.ha_id
    assert client.start_program.call_count == 1
    assert client.start_program.call_args == snapshot


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    ("mock_attr", "error_regex", "get_active_program_side_effect"),
    [
        (
            "get_active_program",
            r"Error.*obtaining.*program.*",
            None,
        ),
        (
            "get_selected_program",
            r"Error.*obtaining.*program.*",
            NoProgramActiveError("error.key"),
        ),
        ("start_program", r"Error.*starting.*program.*", None),
    ],
)
async def test_start_selected_program_and_options_exceptions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    mock_attr: str,
    error_regex: str,
    get_active_program_side_effect: NoProgramActiveError | None,
) -> None:
    """Test error handling when starting the selected program."""
    client.get_active_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
        ),
        side_effect=get_active_program_side_effect,
    )
    client.get_selected_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
        )
    )
    getattr(client, mock_attr).side_effect = HomeConnectError("error.key")

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    with pytest.raises(HomeAssistantError, match=error_regex):
        await hass.services.async_call(
            domain=DOMAIN,
            service="start_selected_program",
            service_data={
                "device_id": device_entry.id,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "get_active_program_side_effect",
    [None, NoProgramActiveError("error.key")],
)
async def test_no_program_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    get_active_program_side_effect: NoProgramActiveError | None,
) -> None:
    """Test handling of no program active error."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "HA_ID")},
    )

    client.get_active_program = AsyncMock(
        return_value=Program(
            key=None,
        ),
        side_effect=get_active_program_side_effect,
    )
    client.get_selected_program = AsyncMock(
        return_value=Program(
            key=None,
        )
    )

    with pytest.raises(HomeAssistantError, match="No program to start"):
        await hass.services.async_call(
            domain=DOMAIN,
            service="start_selected_program",
            service_data={
                "device_id": device_entry.id,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "service_call",
    [
        SERVICE_KV_CALL_PARAMS[0],
        {
            "domain": DOMAIN,
            "service": "start_selected_program",
            "service_data": {},
            "blocking": True,
        },
    ],
)
async def test_services_appliance_not_found(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    service_call: dict[str, Any],
) -> None:
    """Raise a ServiceValidationError when device id does not match."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    service_call = service_call.copy()  # To avoid mutating the original test data
    service_call.setdefault("service_data", {})

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

    with pytest.raises(ServiceValidationError, match=r"Config entry.*not found"):
        await hass.services.async_call(**service_call)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("RANDOM", "ABCD")},
    )
    service_call["service_data"]["device_id"] = device_entry.id

    with pytest.raises(ServiceValidationError, match=r"Appliance.*not found"):
        await hass.services.async_call(**service_call)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS,
)
async def test_services_exception(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service_call: dict[str, Any],
) -> None:
    """Raise a ValueError when device id does not match."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id

    service_name = service_call["service"]
    with pytest.raises(
        HomeAssistantError,
        match=SERVICE_VALIDATION_ERROR_MAPPING[service_name],
    ):
        await hass.services.async_call(**service_call)


async def test_not_possible_to_use_favorite_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Raise a MultipleInvalid when trying to use a favorite program."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "HA_ID")},
    )

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "set_program_and_options",
            {
                "device_id": device_entry.id,
                "affects_to": "selected_program",
                "program": bsh_key_to_translation_key(
                    ProgramKey.BSH_COMMON_FAVORITE_001.value
                ),
            },
            blocking=True,
        )
