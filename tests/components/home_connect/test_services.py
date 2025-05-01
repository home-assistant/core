"""Tests for the Home Connect actions."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

from aiohomeconnect.model import HomeAppliance, OptionKey, ProgramKey, SettingKey
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

DEPRECATED_SERVICE_KV_CALL_PARAMS = [
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
]

SERVICE_KV_CALL_PARAMS = [
    *DEPRECATED_SERVICE_KV_CALL_PARAMS,
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

SERVICE_VALIDATION_ERROR_MAPPING = {
    "set_option_active": r"Error.*setting.*options.*active.*program.*",
    "set_option_selected": r"Error.*setting.*options.*selected.*program.*",
    "change_setting": r"Error.*assigning.*value.*setting.*",
    "pause_program": r"Error.*executing.*command.*",
    "resume_program": r"Error.*executing.*command.*",
    "select_program": r"Error.*selecting.*program.*",
    "start_program": r"Error.*starting.*program.*",
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
@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
async def test_key_value_services(
    service_call: dict[str, Any],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
) -> None:
    """Create and test services."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
    ("service_call", "issue_id"),
    [
        *zip(
            DEPRECATED_SERVICE_KV_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
            ["deprecated_set_program_and_option_actions"]
            * (
                len(DEPRECATED_SERVICE_KV_CALL_PARAMS)
                + len(SERVICE_PROGRAM_CALL_PARAMS)
            ),
            strict=True,
        ),
        *zip(
            SERVICE_COMMAND_CALL_PARAMS,
            ["deprecated_command_actions"] * len(SERVICE_COMMAND_CALL_PARAMS),
            strict=True,
        ),
    ],
)
async def test_programs_and_options_actions_deprecation(
    service_call: dict[str, Any],
    issue_id: str,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test deprecated service keys."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue

    _client = await hass_client()
    resp = await _client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue.issue_id},
    )
    assert resp.status == HTTPStatus.OK
    flow_id = (await resp.json())["flow_id"]
    resp = await _client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0

    await hass.services.async_call(**service_call)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


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
    service_call: dict[str, Any],
    called_method: str,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
    snapshot: SnapshotAssertion,
) -> None:
    """Test recognized options."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
    service_call: dict[str, Any],
    error_regex: str,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
    appliance: HomeAppliance,
) -> None:
    """Test recognized options."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id
    with pytest.raises(HomeAssistantError, match=error_regex):
        await hass.services.async_call(**service_call)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
async def test_services_exception_device_id(
    service_call: dict[str, Any],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
    appliance: HomeAppliance,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Raise a HomeAssistantError when there is an API error."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
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
    SERVICE_KV_CALL_PARAMS + SERVICE_COMMAND_CALL_PARAMS + SERVICE_PROGRAM_CALL_PARAMS,
)
async def test_services_exception(
    service_call: dict[str, Any],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
    appliance: HomeAppliance,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Raise a ValueError when device id does not match."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

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
