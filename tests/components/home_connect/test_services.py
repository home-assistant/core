"""Tests for the Home Connect actions."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

from aiohomeconnect.model import HomeAppliance, SettingKey
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.home_connect.const import DOMAIN
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


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    "service_call",
    SERVICE_KV_CALL_PARAMS,
)
async def test_services_exception_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    service_call: dict[str, Any],
) -> None:
    """Raise a HomeAssistantError when there is an API error."""
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    service_call["service_data"]["device_id"] = device_entry.id

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(**service_call)


async def test_services_appliance_not_found(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Raise a ServiceValidationError when device id does not match."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

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
