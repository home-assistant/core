"""Tests for home_connect number entities."""

from collections.abc import Awaitable, Callable
import random
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
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
    HomeConnectApiError,
    HomeConnectError,
    SelectedProgramNotSetError,
)
from aiohomeconnect.model.program import (
    ProgramDefinitionConstraints,
    ProgramDefinitionOption,
)
from aiohomeconnect.model.setting import SettingConstraints
import pytest

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE as SERVICE_ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


async def test_number(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test number entity."""
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
                    OptionKey.BSH_COMMON_FINISH_IN_RELATIVE,
                    "Integer",
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


@pytest.mark.parametrize("appliance_ha_id", ["FridgeFreezer"], indirect=True)
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
    get_settings_original_mock = client.get_settings

    def get_settings_side_effect(ha_id: str):
        if ha_id == appliance_ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return get_settings_original_mock.return_value

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance_ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)

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
    new_entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert len(new_entity_entries) > len(entity_entries)


@pytest.mark.parametrize("appliance_ha_id", ["FridgeFreezer"], indirect=True)
async def test_number_entity_availabilty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test if number entities availability are based on the appliance connection state."""
    entity_ids = [
        f"{NUMBER_DOMAIN.lower()}.fridgefreezer_refrigerator_temperature",
    ]

    client.get_setting.side_effect = None
    # Setting constrains are not needed for this test
    # so we rise an error to easily test the availability
    client.get_setting = AsyncMock(side_effect=HomeConnectError())
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


@pytest.mark.parametrize("appliance_ha_id", ["FridgeFreezer"], indirect=True)
@pytest.mark.parametrize(
    (
        "entity_id",
        "setting_key",
        "type",
        "expected_state",
        "min_value",
        "max_value",
        "step_size",
        "unit_of_measurement",
    ),
    [
        (
            f"{NUMBER_DOMAIN.lower()}.fridgefreezer_refrigerator_temperature",
            SettingKey.REFRIGERATION_FRIDGE_FREEZER_SETPOINT_TEMPERATURE_REFRIGERATOR,
            "Double",
            8,
            7,
            15,
            0.1,
            "°C",
        ),
        (
            f"{NUMBER_DOMAIN.lower()}.fridgefreezer_refrigerator_temperature",
            SettingKey.REFRIGERATION_FRIDGE_FREEZER_SETPOINT_TEMPERATURE_REFRIGERATOR,
            "Double",
            8,
            7,
            15,
            5,
            "°C",
        ),
    ],
)
async def test_number_entity_functionality(
    appliance_ha_id: str,
    entity_id: str,
    setting_key: SettingKey,
    type: str,
    expected_state: int,
    min_value: int,
    max_value: int,
    step_size: float,
    unit_of_measurement: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test number entity functionality."""
    client.get_setting.side_effect = None
    client.get_setting = AsyncMock(
        return_value=GetSetting(
            key=setting_key,
            raw_key=setting_key.value,
            value="",  # This should not change the value
            unit=unit_of_measurement,
            type=type,
            constraints=SettingConstraints(
                min=min_value,
                max=max_value,
                step_size=step_size if isinstance(step_size, int) else None,
            ),
        )
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == str(expected_state)
    attributes = entity_state.attributes
    assert attributes["min"] == min_value
    assert attributes["max"] == max_value
    assert attributes["step"] == step_size
    assert attributes["unit_of_measurement"] == unit_of_measurement

    value = random.choice(
        [num for num in range(min_value, max_value + 1) if num != expected_state]
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            SERVICE_ATTR_VALUE: value,
        },
    )
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance_ha_id, setting_key=setting_key, value=value
    )
    assert hass.states.is_state(entity_id, str(float(value)))


@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{NUMBER_DOMAIN.lower()}.fridgefreezer_refrigerator_temperature",
            SettingKey.REFRIGERATION_FRIDGE_FREEZER_SETPOINT_TEMPERATURE_REFRIGERATOR,
            "set_setting",
        ),
    ],
)
async def test_number_entity_error(
    entity_id: str,
    setting_key: SettingKey,
    mock_attr: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test number entity error."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=setting_key,
                raw_key=setting_key.value,
                value=DEFAULT_MIN_VALUE,
                constraints=SettingConstraints(
                    min=int(DEFAULT_MIN_VALUE),
                    max=int(DEFAULT_MAX_VALUE),
                    step_size=1,
                ),
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
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                SERVICE_ATTR_VALUE: DEFAULT_MIN_VALUE,
            },
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
    ("appliance_ha_id", "entity_id", "option_key", "min", "max", "step_size", "unit"),
    [
        (
            "Oven",
            "number.oven_setpoint_temperature",
            OptionKey.COOKING_OVEN_SETPOINT_TEMPERATURE,
            50,
            260,
            1,
            "°C",
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_options_functionality(
    entity_id: str,
    option_key: OptionKey,
    appliance_ha_id: str,
    min: int,
    max: int,
    step_size: int,
    unit: str,
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

    async def set_program_option_side_effect(ha_id: str, *_, **kwargs) -> None:
        event_key = EventKey(kwargs["option_key"])
        await client.add_events(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=kwargs["value"],
                                unit=unit,
                            )
                        ]
                    ),
                ),
            ]
        )

    called_mock = AsyncMock(side_effect=set_program_option_side_effect)
    if set_active_program_options_side_effect:
        client.set_active_program_option.side_effect = (
            set_active_program_options_side_effect
        )
    else:
        assert set_selected_program_options_side_effect
        client.set_selected_program_option.side_effect = (
            set_selected_program_options_side_effect
        )
    setattr(client, called_mock_method, called_mock)
    client.get_available_program = AsyncMock(
        return_value=ProgramDefinition(
            ProgramKey.UNKNOWN,
            options=[
                ProgramDefinitionOption(
                    option_key,
                    "Double",
                    unit=unit,
                    constraints=ProgramDefinitionConstraints(
                        min=min,
                        max=max,
                        step_size=step_size,
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
    assert entity_state.attributes["unit_of_measurement"] == unit
    assert entity_state.attributes[ATTR_MIN] == min
    assert entity_state.attributes[ATTR_MAX] == max
    assert entity_state.attributes[ATTR_STEP] == step_size

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, SERVICE_ATTR_VALUE: 80},
    )
    await hass.async_block_till_done()

    assert called_mock.called
    assert called_mock.call_args.args == (appliance_ha_id,)
    assert called_mock.call_args.kwargs == {
        "option_key": option_key,
        "value": 80,
    }
    assert hass.states.is_state(entity_id, "80.0")
