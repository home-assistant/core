"""Tests for home_connect select entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfPrograms,
    ArrayOfSettings,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    OptionKey,
    ProgramDefinition,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import (
    ActiveProgramNotSetError,
    HomeConnectError,
    SelectedProgramNotSetError,
)
from aiohomeconnect.model.program import (
    EnumerateProgram,
    EnumerateProgramConstraints,
    Execution,
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
from aiohomeconnect.model.setting import SettingConstraints
import pytest

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


async def test_select(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test select entity."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_paired_depaired_devices_flow(
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE,
                    "Enumeration",
                )
            ],
        )
    )
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


async def test_connected_devices(
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries


async def test_select_entity_availabilty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test if select entities availability are based on the appliance connection state."""
    entity_ids = [
        "select.washer_active_program",
    ]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE


async def test_filter_programs(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select that only right programs are shown."""
    client.get_all_programs.side_effect = None
    client.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_ECO_50.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_ONLY,
                ),
            ),
            EnumerateProgram(
                key=ProgramKey.UNKNOWN,
                raw_key="an unknown program",
            ),
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_QUICK_45,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_QUICK_45.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.START_ONLY,
                ),
            ),
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_AUTO_1,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_AUTO_1.value,
                constraints=EnumerateProgramConstraints(
                    execution=Execution.SELECT_AND_START,
                ),
            ),
        ]
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get("select.dishwasher_selected_program")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_OPTIONS] == [
        "dishcare_dishwasher_program_eco_50",
        "dishcare_dishwasher_program_auto_1",
    ]

    entity = entity_registry.async_get("select.dishwasher_active_program")
    assert entity
    assert entity.capabilities
    assert entity.capabilities[ATTR_OPTIONS] == [
        "dishcare_dishwasher_program_quick_45",
        "dishcare_dishwasher_program_auto_1",
    ]


@pytest.mark.parametrize(
    (
        "appliance_ha_id",
        "entity_id",
        "expected_initial_state",
        "mock_method",
        "program_key",
        "program_to_set",
        "event_key",
    ),
    [
        (
            "Dishwasher",
            "select.dishwasher_selected_program",
            "dishcare_dishwasher_program_auto_1",
            "set_selected_program",
            ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            "dishcare_dishwasher_program_eco_50",
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ),
        (
            "Dishwasher",
            "select.dishwasher_active_program",
            "dishcare_dishwasher_program_auto_1",
            "start_program",
            ProgramKey.DISHCARE_DISHWASHER_ECO_50,
            "dishcare_dishwasher_program_eco_50",
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_select_program_functionality(
    appliance_ha_id: str,
    entity_id: str,
    expected_initial_state: str,
    mock_method: str,
    program_key: ProgramKey,
    program_to_set: str,
    event_key: EventKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test select functionality."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, expected_initial_state)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: program_to_set},
    )
    await hass.async_block_till_done()
    getattr(client, mock_method).assert_awaited_once_with(
        appliance_ha_id, program_key=program_key
    )
    assert hass.states.is_state(entity_id, program_to_set)

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.NOTIFY,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value="A not known program",
                        )
                    ]
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_UNKNOWN)


@pytest.mark.parametrize(
    (
        "entity_id",
        "program_to_set",
        "mock_attr",
        "exception_match",
    ),
    [
        (
            "select.dishwasher_selected_program",
            "dishcare_dishwasher_program_eco_50",
            "set_selected_program",
            r"Error.*select.*program.*",
        ),
        (
            "select.dishwasher_active_program",
            "dishcare_dishwasher_program_eco_50",
            "start_program",
            r"Error.*start.*program.*",
        ),
    ],
)
async def test_select_exception_handling(
    entity_id: str,
    program_to_set: str,
    mock_attr: str,
    exception_match: str,
    hass: HomeAssistant,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test exception handling."""
    client_with_exception.get_all_programs.side_effect = None
    client_with_exception.get_all_programs.return_value = ArrayOfPrograms(
        [
            EnumerateProgram(
                key=ProgramKey.DISHCARE_DISHWASHER_ECO_50,
                raw_key=ProgramKey.DISHCARE_DISHWASHER_ECO_50.value,
            )
        ]
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, STATE_UNKNOWN)

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        await getattr(client_with_exception, mock_attr)()

    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {"entity_id": entity_id, "option": program_to_set},
            blocking=True,
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2


@pytest.mark.parametrize("appliance_ha_id", ["Hood"], indirect=True)
@pytest.mark.parametrize(
    (
        "entity_id",
        "setting_key",
        "expected_options",
        "value_to_set",
        "expected_value_call_arg",
    ),
    [
        (
            "select.hood_functional_light_color_temperature",
            SettingKey.COOKING_HOOD_COLOR_TEMPERATURE,
            {
                "cooking_hood_enum_type_color_temperature_warm",
                "cooking_hood_enum_type_color_temperature_neutral",
                "cooking_hood_enum_type_color_temperature_cold",
            },
            "cooking_hood_enum_type_color_temperature_neutral",
            "Cooking.Hood.EnumType.ColorTemperature.neutral",
        ),
        (
            "select.hood_ambient_light_color",
            SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR,
            {
                "b_s_h_common_enum_type_ambient_light_color_custom_color",
                *[str(i) for i in range(1, 100)],
            },
            "42",
            "BSH.Common.EnumType.AmbientLightColor.Color42",
        ),
    ],
)
async def test_select_functionality(
    appliance_ha_id: str,
    entity_id: str,
    setting_key: SettingKey,
    expected_options: set[str],
    value_to_set: str,
    expected_value_call_arg: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test select functionality."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert set(entity_state.attributes[ATTR_OPTIONS]) == expected_options

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": value_to_set},
    )
    await hass.async_block_till_done()

    client.set_setting.assert_called_once()
    assert client.set_setting.call_args.args == (appliance_ha_id,)
    assert client.set_setting.call_args.kwargs == {
        "setting_key": setting_key,
        "value": expected_value_call_arg,
    }
    assert hass.states.is_state(entity_id, value_to_set)


@pytest.mark.parametrize("appliance_ha_id", ["Hood"], indirect=True)
@pytest.mark.parametrize(
    (
        "entity_id",
        "test_setting_key",
        "allowed_values",
        "expected_options",
    ),
    [
        (
            "select.hood_ambient_light_color",
            SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR,
            [f"BSH.Common.EnumType.AmbientLightColor.Color{i}" for i in range(50)],
            {str(i) for i in range(1, 50)},
        ),
    ],
)
async def test_fetch_allowed_values(
    appliance_ha_id: str,
    entity_id: str,
    test_setting_key: SettingKey,
    allowed_values: list[str | None],
    expected_options: set[str],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test fetch allowed values."""
    original_get_setting_side_effect = client.get_setting

    async def get_setting_side_effect(
        ha_id: str, setting_key: SettingKey
    ) -> GetSetting:
        if ha_id != appliance_ha_id or setting_key != test_setting_key:
            return await original_get_setting_side_effect(ha_id, setting_key)
        return GetSetting(
            key=test_setting_key,
            raw_key=test_setting_key.value,
            value="",  # Not important
            constraints=SettingConstraints(
                allowed_values=allowed_values,
            ),
        )

    client.get_setting = AsyncMock(side_effect=get_setting_side_effect)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert set(entity_state.attributes[ATTR_OPTIONS]) == expected_options


@pytest.mark.parametrize(
    ("entity_id", "setting_key", "allowed_value", "value_to_set", "mock_attr"),
    [
        (
            "select.hood_functional_light_color_temperature",
            SettingKey.COOKING_HOOD_COLOR_TEMPERATURE,
            "Cooking.Hood.EnumType.ColorTemperature.neutral",
            "cooking_hood_enum_type_color_temperature_neutral",
            "set_setting",
        ),
    ],
)
async def test_select_entity_error(
    entity_id: str,
    setting_key: SettingKey,
    allowed_value: str,
    value_to_set: str,
    mock_attr: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test select entity error."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=setting_key,
                raw_key=setting_key.value,
                value=value_to_set,
                constraints=SettingConstraints(allowed_values=[allowed_value]),
            )
        ]
    )
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(HomeConnectError):
        await getattr(client_with_exception, mock_attr)()

    with pytest.raises(
        HomeAssistantError, match=r"Error.*assign.*value.*to.*setting.*"
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": value_to_set},
            blocking=True,
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2


@pytest.mark.parametrize(
    (
        "set_active_program_options_side_effect",
        "set_selected_program_options_side_effect",
        "called_mock_method",
    ),
    [
        (
            None,
            SelectedProgramNotSetError("error.key"),
            "set_active_program_option",
        ),
        (
            ActiveProgramNotSetError("error.key"),
            None,
            "set_selected_program_option",
        ),
    ],
)
@pytest.mark.parametrize(
    ("entity_id", "option_key", "allowed_values", "expected_options"),
    [
        (
            "select.washer_temperature",
            OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE,
            None,
            {
                "laundry_care_washer_enum_type_temperature_cold",
                "laundry_care_washer_enum_type_temperature_g_c_20",
                "laundry_care_washer_enum_type_temperature_g_c_30",
                "laundry_care_washer_enum_type_temperature_g_c_40",
                "laundry_care_washer_enum_type_temperature_g_c_50",
                "laundry_care_washer_enum_type_temperature_g_c_60",
                "laundry_care_washer_enum_type_temperature_g_c_70",
                "laundry_care_washer_enum_type_temperature_g_c_80",
                "laundry_care_washer_enum_type_temperature_g_c_90",
                "laundry_care_washer_enum_type_temperature_ul_cold",
                "laundry_care_washer_enum_type_temperature_ul_warm",
                "laundry_care_washer_enum_type_temperature_ul_hot",
                "laundry_care_washer_enum_type_temperature_ul_extra_hot",
            },
        ),
        (
            "select.washer_temperature",
            OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE,
            [
                "LaundryCare.Washer.EnumType.Temperature.UlCold",
                "LaundryCare.Washer.EnumType.Temperature.UlWarm",
                "LaundryCare.Washer.EnumType.Temperature.UlHot",
                "LaundryCare.Washer.EnumType.Temperature.UlExtraHot",
            ],
            {
                "laundry_care_washer_enum_type_temperature_ul_cold",
                "laundry_care_washer_enum_type_temperature_ul_warm",
                "laundry_care_washer_enum_type_temperature_ul_hot",
                "laundry_care_washer_enum_type_temperature_ul_extra_hot",
            },
        ),
    ],
)
async def test_options_functionality(
    entity_id: str,
    option_key: OptionKey,
    allowed_values: list[str | None] | None,
    expected_options: set[str],
    appliance_ha_id: str,
    set_active_program_options_side_effect: ActiveProgramNotSetError | None,
    set_selected_program_options_side_effect: SelectedProgramNotSetError | None,
    called_mock_method: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test options functionality."""
    if set_active_program_options_side_effect:
        client.set_active_program_option.side_effect = (
            set_active_program_options_side_effect
        )
    else:
        assert set_selected_program_options_side_effect
        client.set_selected_program_option.side_effect = (
            set_selected_program_options_side_effect
        )
    called_mock: AsyncMock = getattr(client, called_mock_method)
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    option_key,
                    "Enumeration",
                    constraints=ProgramDefinitionConstraints(
                        allowed_values=allowed_values
                    ),
                )
            ],
        )
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert set(entity_state.attributes[ATTR_OPTIONS]) == expected_options

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "laundry_care_washer_enum_type_temperature_ul_warm",
        },
    )
    await hass.async_block_till_done()

    assert called_mock.called
    assert called_mock.call_args.args == (appliance_ha_id,)
    assert called_mock.call_args.kwargs == {
        "option_key": option_key,
        "value": "LaundryCare.Washer.EnumType.Temperature.UlWarm",
    }
    assert hass.states.is_state(
        entity_id, "laundry_care_washer_enum_type_temperature_ul_warm"
    )
