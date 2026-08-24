"""Tests for the Home Connect actions."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.model import (
    HomeAppliance,
    Option,
    OptionKey,
    Program,
    ProgramDefinition,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectError, NoProgramActiveError
from aiohomeconnect.model.image import ArrayOfImages, Image
from aiohomeconnect.model.program import ProgramDefinitionOption
import pytest
from syrupy.assertion import SnapshotAssertion
from voluptuous.error import MultipleInvalid

from homeassistant.components import home_connect
from homeassistant.components.home_connect.const import (
    DOMAIN,
    PROGRAM_ENUM_OPTIONS,
    TRANSLATION_KEYS_PROGRAMS_MAP,
)
from homeassistant.components.home_connect.services import PROGRAM_OPTIONS
from homeassistant.components.home_connect.utils import bsh_key_to_translation_key
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util.yaml import load_yaml_dict

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

IMAGE_ENTITY_ID = "image.fridgefreezer_interior_right_camera"


@pytest.fixture
def platforms(request: pytest.FixtureRequest) -> list[Platform]:
    """Fixture to specify platforms to test."""
    if hasattr(request, "param") and request.param:
        return request.param
    return []


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
            "consumer_products_coffee_maker_option_bean_amount": (
                "consumer_products_coffee_maker_enum_type_bean_amount_normal"
            ),
        },
        "blocking": True,
    },
    {
        "domain": DOMAIN,
        "service": "set_program_and_options",
        "service_data": {
            "device_id": "DEVICE_ID",
            "affects_to": "active_program",
            "consumer_products_coffee_maker_option_coffee_milk_ratio": (
                "consumer_products_coffee_maker_enum_type_coffee_milk_ratio_50_percent"
            ),
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


def test_services_yaml_set_program_and_options_program_keys() -> None:
    """Test that all program keys in services.yaml exist in the translation map."""
    services = load_yaml_dict(f"{home_connect.__path__[0]}/services.yaml")
    yaml_programs = set(
        services["set_program_and_options"]["fields"]["program"]["selector"]["select"][
            "options"
        ]
    )

    assert yaml_programs <= set(TRANSLATION_KEYS_PROGRAMS_MAP.keys())


def test_services_yaml_set_program_and_options_option_keys() -> None:
    """Test that all program keys in services.yaml exist in the translation map."""
    services = load_yaml_dict(f"{home_connect.__path__[0]}/services.yaml")
    groups = services["set_program_and_options"]["fields"]
    groups.pop("device_id")
    groups.pop("affects_to")
    groups.pop("program")
    for group in groups.values():
        for option, option_data in group["fields"].items():
            assert option in PROGRAM_ENUM_OPTIONS or option in PROGRAM_OPTIONS, (
                f"{option} is missing from both"
                " PROGRAM_ENUM_OPTIONS and PROGRAM_OPTIONS"
            )
            if option in PROGRAM_ENUM_OPTIONS:
                enum_values = set(PROGRAM_ENUM_OPTIONS[option][1])
                assert enum_values == set(
                    option_data["selector"]["select"]["options"]
                ), (
                    f"Options for {option} do not match between"
                    " services.yaml and constants.py"
                )
                assert "example" in option_data, (
                    f"Example value for {option} is missing"
                )
                assert option_data["example"] in enum_values, (
                    f"Example value for {option} is not a valid option"
                )


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
    "non_writable_options",
    [
        None,
        [
            Option(
                key=OptionKey.BSH_COMMON_WATER_FORECAST,
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
    non_writable_options: list[Option] | None,
    get_active_program_side_effect: NoProgramActiveError | None,
    get_selected_program_call_count: int,
    snapshot: SnapshotAssertion,
) -> None:
    """Test starting the selected program with optional parameter overrides."""
    client.get_active_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[*(options_already_set or []), *(non_writable_options or [])]
            if options_already_set or non_writable_options
            else None,
        ),
        side_effect=get_active_program_side_effect,
    )
    client.get_selected_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[*(options_already_set or []), *(non_writable_options or [])]
            if options_already_set or non_writable_options
            else None,
        )
    )
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[
                ProgramDefinitionOption(
                    key=OptionKey.BSH_COMMON_FINISH_IN_RELATIVE,
                    type="integer",
                ),
                ProgramDefinitionOption(
                    key=OptionKey.BSH_COMMON_START_IN_RELATIVE,
                    type="integer",
                ),
                *[
                    ProgramDefinitionOption(
                        key=option.key,
                        type="boolean",  # Not relevant
                    )
                    for option in options_already_set or []
                ],
            ],
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


@pytest.mark.parametrize(
    "get_active_program_side_effect", [None, NoProgramActiveError("error.key")]
)
@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
async def test_start_select_program_non_writtable_options_discarded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    get_active_program_side_effect: NoProgramActiveError | None,
) -> None:
    """Test that non-writable options are discarded when starting the selected program."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_active_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[
                Option(
                    key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
                    value=True,
                ),
                Option(
                    key=OptionKey.BSH_COMMON_ENERGY_FORECAST,
                    value=True,
                ),
            ],
        ),
        side_effect=get_active_program_side_effect,
    )
    client.get_selected_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[
                Option(
                    key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
                    value=True,
                ),
                Option(
                    key=OptionKey.BSH_COMMON_ENERGY_FORECAST,
                    value=True,
                ),
            ],
        )
    )
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[
                ProgramDefinitionOption(
                    key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
                    type="boolean",
                )
            ],
        )
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    await hass.services.async_call(
        domain=DOMAIN,
        service="start_selected_program",
        service_data={
            "device_id": device_entry.id,
        },
        blocking=True,
    )

    client.start_program.assert_awaited_once_with(
        appliance.ha_id,
        program_key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
        options=[
            Option(
                key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
                value=True,
            )
        ],
    )


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


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_start_selected_program_user_option_not_writable_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """A user-passed option that the program does not list as writable must raise."""
    client.get_active_program = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
        ),
    )
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[],
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )

    with pytest.raises(
        HomeAssistantError,
        match=r".*BSH.Common.Option.StartInRelative.*is not writable",
    ):
        await hass.services.async_call(
            domain=DOMAIN,
            service="start_selected_program",
            service_data={
                "device_id": device_entry.id,
                "b_s_h_common_option_start_in_relative": 1800,
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


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    ("temperature_option", "service_option"),
    [
        pytest.param(
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_SETPOINT_TEMPERATURE,
            "heating_ventilation_air_conditioning_air_conditioner_option_setpoint_temperature",
            id="air_conditioner_setpoint_temperature",
        ),
        pytest.param(
            OptionKey.COOKING_OVEN_SETPOINT_TEMPERATURE,
            "cooking_oven_option_setpoint_temperature",
            id="oven_setpoint_temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    ("affects_to", "program", "get_program_information_method", "method_call"),
    [
        pytest.param(
            "active_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "start_program",
            id="start_program",
        ),
        pytest.param(
            "selected_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "set_selected_program",
            id="select_program",
        ),
        pytest.param(
            "active_program",
            None,
            "get_active_program",
            "set_active_program_options",
            id="set_active_program_options",
        ),
        pytest.param(
            "selected_program",
            None,
            "get_selected_program",
            "set_selected_program_options",
            id="set_selected_program_options",
        ),
    ],
)
@pytest.mark.parametrize(
    ("option_units", "expected_value"),
    [
        pytest.param("°C", 35, id="celsius"),
        pytest.param("°F", 95, id="fahrenheit"),
    ],
)
async def test_temperature_options_convert(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    affects_to: str,
    program: str | None,
    get_program_information_method: str,
    method_call: str,
    temperature_option: OptionKey,
    service_option: str,
    option_units: str,
    expected_value: int,
) -> None:
    """Test that temperature options are converted correctly.

    Note: The program and the options used in this test aren't related.
    """
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    async def test(args: Any, kwargs: Any) -> None:
        pass

    get_program_information_method_mock = AsyncMock(
        return_value=Program(
            key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            options=[Option(key=temperature_option, value=0, unit=option_units)],
        ),
        wraps=test,
    )
    setattr(
        client,
        get_program_information_method,
        get_program_information_method_mock,
    )
    # start_program and set_selected_program side effects
    # does break the await counts. To avoid that mocks are reset.
    setattr(client, method_call, AsyncMock())

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )
    service_data = {
        "device_id": device_entry.id,
        "affects_to": affects_to,
        service_option: 35,
    }
    if program:
        service_data["program"] = program

    await hass.services.async_call(
        DOMAIN,
        "set_program_and_options",
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()

    kwargs = getattr(client, method_call).call_args.kwargs
    call_options: list[Option] = (
        kwargs.get("options") or kwargs["array_of_options"].options
    )
    assert call_options[0].value == expected_value
    get_program_information_method_mock.assert_awaited_once()
    assert get_program_information_method_mock.await_args.args[0] == appliance.ha_id
    assert get_program_information_method_mock.await_args.kwargs.get("program_key") is (
        ProgramKey.DISHCARE_DISHWASHER_ECO_50 if program else None
    )


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    "service_option",
    [
        pytest.param(
            "heating_ventilation_air_conditioning_air_conditioner_option_setpoint_temperature",
            id="air_conditioner_setpoint_temperature",
        ),
        pytest.param(
            "cooking_oven_option_setpoint_temperature",
            id="oven_setpoint_temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    ("affects_to", "program", "get_program_information_method", "method_call"),
    [
        pytest.param(
            "active_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "start_program",
            id="start_program",
        ),
        pytest.param(
            "selected_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "set_selected_program",
            id="select_program",
        ),
        pytest.param(
            "active_program",
            None,
            "get_active_program",
            "set_active_program_options",
            id="set_active_program_options",
        ),
        pytest.param(
            "selected_program",
            None,
            "get_selected_program",
            "set_selected_program_options",
            id="set_selected_program_options",
        ),
    ],
)
@pytest.mark.parametrize("options", [[], None])
async def test_temperature_options_convert_missing_option(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    affects_to: str,
    program: str | None,
    get_program_information_method: str,
    method_call: str,
    service_option: str,
    options: list[Option] | None,
) -> None:
    """Test that default units are used when the option is missing.

    Note: The program and the options used in this test aren't related.
    """
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    setattr(
        client,
        get_program_information_method,
        AsyncMock(
            return_value=Program(
                key=ProgramKey.DISHCARE_DISHWASHER_ECO_50, options=options
            )
        ),
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )
    service_data = {
        "device_id": device_entry.id,
        "affects_to": affects_to,
        service_option: 35,
    }
    if program:
        service_data["program"] = program

    await hass.services.async_call(
        DOMAIN,
        "set_program_and_options",
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()

    kwargs = getattr(client, method_call).call_args.kwargs
    call_options: list[Option] = (
        kwargs.get("options") or kwargs["array_of_options"].options
    )
    assert call_options[0].value == 35


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    "service_option",
    [
        pytest.param(
            "heating_ventilation_air_conditioning_air_conditioner_option_setpoint_temperature",
            id="air_conditioner_setpoint_temperature",
        ),
        pytest.param(
            "cooking_oven_option_setpoint_temperature",
            id="oven_setpoint_temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    ("affects_to", "program", "get_program_information_method", "method_call"),
    [
        pytest.param(
            "active_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "start_program",
            id="start_program",
        ),
        pytest.param(
            "selected_program",
            "dishcare_dishwasher_program_eco_50",
            "get_available_program",
            "set_selected_program",
            id="select_program",
        ),
        pytest.param(
            "active_program",
            None,
            "get_active_program",
            "set_active_program_options",
            id="set_active_program_options",
        ),
        pytest.param(
            "selected_program",
            None,
            "get_selected_program",
            "set_selected_program_options",
            id="set_selected_program_options",
        ),
    ],
)
async def test_temperature_options_convert_api_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    affects_to: str,
    program: str | None,
    get_program_information_method: str,
    method_call: str,
    service_option: str,
) -> None:
    """Test that default units are used on API error.

    Note: The program and the options used in this test aren't related.
    """
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    setattr(
        client,
        get_program_information_method,
        AsyncMock(side_effect=HomeConnectError("error.key")),
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance.ha_id)},
    )
    service_data = {
        "device_id": device_entry.id,
        "affects_to": affects_to,
        service_option: 35,
    }
    if program:
        service_data["program"] = program

    await hass.services.async_call(
        DOMAIN,
        "set_program_and_options",
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()

    kwargs = getattr(client, method_call).call_args.kwargs
    call_options: list[Option] = (
        kwargs.get("options") or kwargs["array_of_options"].options
    )
    assert call_options[0].value == 35


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]], indirect=True)
@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_download_images_service(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    tmp_path: Path,
) -> None:
    """Test downloading images for matching image entity key."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        ),
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.DoorRightRC",
            image_key="image_key_2",
            preview_image_key="preview_image_key_2",
            timestamp=1785978000000,
            quality="good",
        ),
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_3",
            preview_image_key="preview_image_key_3",
            timestamp=1785981600000,
            quality="good",
        ),
    ]
    image_data = {
        "image_key_1": b"image_data_1",
        "image_key_3": b"image_data_3",
    }

    async def mock_get_image(_: str, *, image_key: str) -> bytes:
        return image_data[image_key]

    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    client.get_image = AsyncMock(wraps=mock_get_image)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()
    client.get_image.reset_mock()

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            DOMAIN,
            "download_images",
            {
                "entity_id": IMAGE_ENTITY_ID,
                "folder_name": str(tmp_path),
            },
            blocking=True,
        )

    client.get_images.assert_awaited_once_with(appliance.ha_id)
    assert client.get_image.await_count == 2
    client.get_image.assert_any_call(appliance.ha_id, image_key="image_key_1")
    client.get_image.assert_any_call(appliance.ha_id, image_key="image_key_3")

    expected_files = {
        f"{datetime.fromtimestamp(image.timestamp / 1000).strftime('%Y%m%d_%H%M%S')}.jpg"
        for image in images
        if image.key == "Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC"
    }
    assert {path.name for path in tmp_path.glob("*.jpg")} == expected_files


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]], indirect=True)
@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_download_images_service_with_time_filters(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    tmp_path: Path,
) -> None:
    """Test downloading images with from/to filters."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        ),
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_2",
            preview_image_key="preview_image_key_2",
            timestamp=1785978000000,
            quality="good",
        ),
    ]

    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    client.get_image = AsyncMock(return_value=b"image_data_2")

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()
    client.get_image.reset_mock()

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            DOMAIN,
            "download_images",
            {
                "entity_id": IMAGE_ENTITY_ID,
                "folder_name": str(tmp_path),
                "from": datetime.fromtimestamp(images[1].timestamp / 1000),
                "to": datetime.fromtimestamp(images[1].timestamp / 1000),
            },
            blocking=True,
        )

    client.get_images.assert_awaited_once_with(appliance.ha_id)
    client.get_image.assert_awaited_once_with(appliance.ha_id, image_key="image_key_2")

    expected_filename = f"{datetime.fromtimestamp(images[1].timestamp / 1000).strftime('%Y%m%d_%H%M%S')}.jpg"
    assert {path.name for path in tmp_path.glob("*.jpg")} == {expected_filename}


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]], indirect=True)
@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_download_images_service_no_access_to_path(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test download_images fails when target path is not allowlisted."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        )
    ]

    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    client.get_image = AsyncMock(return_value=b"image_data_1")

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()

    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_images",
            {
                "entity_id": IMAGE_ENTITY_ID,
                "folder_name": "/forbidden",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_access_to_path"
    client.get_images.assert_not_awaited()


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]], indirect=True)
@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_download_images_service_get_image_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    tmp_path: Path,
) -> None:
    """Test download_images handles API errors when fetching image bytes."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        )
    ]

    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    client.get_image = AsyncMock(side_effect=HomeConnectError("error.key"))

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()
    client.get_image.reset_mock()

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_images",
            {
                "entity_id": IMAGE_ENTITY_ID,
                "folder_name": str(tmp_path),
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "fetch_image_error"


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]], indirect=True)
@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_download_images_service_cannot_write(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    tmp_path: Path,
) -> None:
    """Test download_images handles filesystem write errors."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        )
    ]

    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    client.get_image = AsyncMock(return_value=b"image_data_1")

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()
    client.get_image.reset_mock()

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch.object(hass, "async_add_executor_job", side_effect=OSError),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_images",
            {
                "entity_id": IMAGE_ENTITY_ID,
                "folder_name": str(tmp_path),
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "cannot_write"
