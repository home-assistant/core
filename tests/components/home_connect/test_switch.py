"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
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
    HomeAppliance,
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
from aiohomeconnect.model.program import EnumerateProgram, ProgramDefinitionOption
from aiohomeconnect.model.setting import SettingConstraints
import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.home_connect.const import (
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STANDBY,
    DOMAIN,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_paired_depaired_devices_flow(
    appliance: HomeAppliance,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
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
                    OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE,
                    "Boolean",
                )
            ],
        )
    )
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize(
    ("appliance", "keys_to_check"),
    [
        (
            "Washer",
            (
                SettingKey.BSH_COMMON_POWER_STATE,
                SettingKey.BSH_COMMON_CHILD_LOCK,
                "Program Cotton",
            ),
        )
    ],
    indirect=["appliance"],
)
async def test_connected_devices(
    appliance: HomeAppliance,
    keys_to_check: tuple,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_settings_original_mock = client.get_settings
    get_all_programs_mock = client.get_all_programs

    async def get_settings_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_settings_original_mock.side_effect(ha_id)

    async def get_all_programs_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_all_programs_mock.side_effect(ha_id)

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    client.get_all_programs = AsyncMock(side_effect=get_all_programs_side_effect)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock
    client.get_all_programs = get_all_programs_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for key in keys_to_check:
        assert entity_registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
async def test_switch_entity_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    appliance: HomeAppliance,
) -> None:
    """Test if switch entities availability are based on the appliance connection state."""
    entity_ids = [
        "switch.dishwasher_power",
        "switch.dishwasher_child_lock",
        "switch.dishwasher_program_eco50",
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
                appliance.ha_id,
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
                appliance.ha_id,
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


@pytest.mark.parametrize(
    (
        "entity_id",
        "service",
        "settings_key_arg",
        "setting_value_arg",
        "state",
        "appliance",
    ),
    [
        (
            "switch.dishwasher_child_lock",
            SERVICE_TURN_ON,
            SettingKey.BSH_COMMON_CHILD_LOCK,
            True,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_child_lock",
            SERVICE_TURN_OFF,
            SettingKey.BSH_COMMON_CHILD_LOCK,
            False,
            STATE_OFF,
            "Dishwasher",
        ),
    ],
    indirect=["appliance"],
)
async def test_switch_functionality(
    entity_id: str,
    settings_key_arg: SettingKey,
    setting_value_arg: Any,
    service: str,
    state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    client: MagicMock,
) -> None:
    """Test switch functionality."""

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id})
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance.ha_id, setting_key=settings_key_arg, value=setting_value_arg
    )
    assert hass.states.is_state(entity_id, state)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "program_key", "initial_state", "appliance"),
    [
        (
            "switch.dryer_program_mix",
            ProgramKey.LAUNDRY_CARE_DRYER_MIX,
            STATE_OFF,
            "Dryer",
        ),
        (
            "switch.dryer_program_cotton",
            ProgramKey.LAUNDRY_CARE_DRYER_COTTON,
            STATE_ON,
            "Dryer",
        ),
    ],
    indirect=["appliance"],
)
async def test_program_switch_functionality(
    entity_id: str,
    program_key: ProgramKey,
    initial_state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    client: MagicMock,
) -> None:
    """Test switch functionality."""

    async def mock_stop_program(ha_id: str) -> None:
        """Mock stop program."""
        await client.add_events(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                                raw_key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=ProgramKey.UNKNOWN,
                            )
                        ]
                    ),
                ),
            ]
        )

    client.stop_program = AsyncMock(side_effect=mock_stop_program)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, initial_state)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_ON)
    client.start_program.assert_awaited_once_with(
        appliance.ha_id, program_key=program_key
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_OFF)
    client.stop_program.assert_awaited_once_with(appliance.ha_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "entity_id",
        "service",
        "mock_attr",
        "exception_match",
    ),
    [
        (
            "switch.dishwasher_program_eco50",
            SERVICE_TURN_ON,
            "start_program",
            r"Error.*start.*program.*",
        ),
        (
            "switch.dishwasher_program_eco50",
            SERVICE_TURN_OFF,
            "stop_program",
            r"Error.*stop.*program.*",
        ),
        (
            "switch.dishwasher_power",
            SERVICE_TURN_OFF,
            "set_setting",
            r"Error.*turn.*off.*",
        ),
        (
            "switch.dishwasher_power",
            SERVICE_TURN_ON,
            "set_setting",
            r"Error.*turn.*on.*",
        ),
        (
            "switch.dishwasher_child_lock",
            SERVICE_TURN_ON,
            "set_setting",
            r"Error.*turn.*on.*",
        ),
        (
            "switch.dishwasher_child_lock",
            SERVICE_TURN_OFF,
            "set_setting",
            r"Error.*turn.*off.*",
        ),
    ],
)
async def test_switch_exception_handling(
    entity_id: str,
    service: str,
    mock_attr: str,
    exception_match: str,
    hass: HomeAssistant,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
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
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=SettingKey.BSH_COMMON_CHILD_LOCK,
                raw_key=SettingKey.BSH_COMMON_CHILD_LOCK.value,
                value=False,
            ),
            GetSetting(
                key=SettingKey.BSH_COMMON_POWER_STATE,
                raw_key=SettingKey.BSH_COMMON_POWER_STATE.value,
                value=BSH_POWER_ON,
                constraints=SettingConstraints(
                    allowed_values=[BSH_POWER_ON, BSH_POWER_OFF]
                ),
            ),
        ]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        await getattr(client_with_exception, mock_attr)()

    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2


@pytest.mark.parametrize(
    ("entity_id", "status", "service", "state", "appliance"),
    [
        (
            "switch.fridgefreezer_freezer_super_mode",
            {SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER: True},
            SERVICE_TURN_ON,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "switch.fridgefreezer_freezer_super_mode",
            {SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER: False},
            SERVICE_TURN_OFF,
            STATE_OFF,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
async def test_ent_desc_switch_functionality(
    entity_id: str,
    status: dict,
    service: str,
    state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    client: MagicMock,
) -> None:
    """Test switch functionality - entity description setup."""

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id})
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize(
    (
        "entity_id",
        "status",
        "service",
        "mock_attr",
        "appliance",
        "exception_match",
    ),
    [
        (
            "switch.fridgefreezer_freezer_super_mode",
            {SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER: ""},
            SERVICE_TURN_ON,
            "set_setting",
            "FridgeFreezer",
            r"Error.*turn.*on.*",
        ),
        (
            "switch.fridgefreezer_freezer_super_mode",
            {SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER: ""},
            SERVICE_TURN_OFF,
            "set_setting",
            "FridgeFreezer",
            r"Error.*turn.*off.*",
        ),
    ],
    indirect=["appliance"],
)
async def test_ent_desc_switch_exception_handling(
    entity_id: str,
    status: dict[SettingKey, str],
    service: str,
    mock_attr: str,
    exception_match: str,
    hass: HomeAssistant,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    config_entry: MockConfigEntry,
    appliance: HomeAppliance,
    client_with_exception: MagicMock,
) -> None:
    """Test switch exception handling - entity description setup."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=key,
                raw_key=key.value,
                value=value,
            )
            for key, value in status.items()
        ]
    )
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    # Assert that an exception is called.
    with pytest.raises(HomeConnectError):
        await client_with_exception.set_setting()
    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert client_with_exception.set_setting.call_count == 2


@pytest.mark.parametrize(
    (
        "entity_id",
        "allowed_values",
        "service",
        "setting_value_arg",
        "power_state",
        "appliance",
    ),
    [
        (
            "switch.dishwasher_power",
            [BSH_POWER_ON, BSH_POWER_OFF],
            SERVICE_TURN_ON,
            BSH_POWER_ON,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            [BSH_POWER_ON, BSH_POWER_OFF],
            SERVICE_TURN_OFF,
            BSH_POWER_OFF,
            STATE_OFF,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            [BSH_POWER_ON, BSH_POWER_STANDBY],
            SERVICE_TURN_ON,
            BSH_POWER_ON,
            STATE_ON,
            "Dishwasher",
        ),
        (
            "switch.dishwasher_power",
            [BSH_POWER_ON, BSH_POWER_STANDBY],
            SERVICE_TURN_OFF,
            BSH_POWER_STANDBY,
            STATE_OFF,
            "Dishwasher",
        ),
    ],
    indirect=["appliance"],
)
async def test_power_switch(
    entity_id: str,
    allowed_values: list[str | None] | None,
    service: str,
    setting_value_arg: str,
    power_state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    client: MagicMock,
) -> None:
    """Test power switch functionality."""
    client.get_settings.side_effect = None
    client.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=SettingKey.BSH_COMMON_POWER_STATE,
                raw_key=SettingKey.BSH_COMMON_POWER_STATE.value,
                value="",
                constraints=SettingConstraints(
                    allowed_values=allowed_values,
                ),
            )
        ]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id})
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance.ha_id,
        setting_key=SettingKey.BSH_COMMON_POWER_STATE,
        value=setting_value_arg,
    )
    assert hass.states.is_state(entity_id, power_state)


@pytest.mark.parametrize(
    ("initial_value"),
    [
        (BSH_POWER_OFF),
        (BSH_POWER_STANDBY),
    ],
)
async def test_power_switch_fetch_off_state_from_current_value(
    initial_value: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
) -> None:
    """Test power switch functionality to fetch the off state from the current value."""
    client.get_settings.side_effect = None
    client.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=SettingKey.BSH_COMMON_POWER_STATE,
                raw_key=SettingKey.BSH_COMMON_POWER_STATE.value,
                value=initial_value,
            )
        ]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.states.is_state("switch.dishwasher_power", STATE_OFF)


@pytest.mark.parametrize(
    ("entity_id", "allowed_values", "service", "exception_match"),
    [
        (
            "switch.dishwasher_power",
            [BSH_POWER_ON],
            SERVICE_TURN_OFF,
            r".*not support.*turn.*off.*",
        ),
        (
            "switch.dishwasher_power",
            None,
            SERVICE_TURN_OFF,
            r".*Unable.*turn.*off.*support.*not.*determined.*",
        ),
        (
            "switch.dishwasher_power",
            HomeConnectError(),
            SERVICE_TURN_OFF,
            r".*Unable.*turn.*off.*support.*not.*determined.*",
        ),
    ],
)
async def test_power_switch_service_validation_errors(
    entity_id: str,
    allowed_values: list[str | None] | None | HomeConnectError,
    service: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    exception_match: str,
    client: MagicMock,
) -> None:
    """Test power switch functionality validation errors."""
    client.get_settings.side_effect = None
    if isinstance(allowed_values, HomeConnectError):
        exception = allowed_values
        client.get_settings.return_value = ArrayOfSettings(
            [
                GetSetting(
                    key=SettingKey.BSH_COMMON_POWER_STATE,
                    raw_key=SettingKey.BSH_COMMON_POWER_STATE.value,
                    value=BSH_POWER_ON,
                )
            ]
        )
        client.get_setting = AsyncMock(side_effect=exception)
    else:
        setting = GetSetting(
            key=SettingKey.BSH_COMMON_POWER_STATE,
            raw_key=SettingKey.BSH_COMMON_POWER_STATE.value,
            value=BSH_POWER_ON,
            constraints=SettingConstraints(
                allowed_values=allowed_values,
            ),
        )
        client.get_settings.return_value = ArrayOfSettings([setting])
        client.get_setting = AsyncMock(return_value=setting)

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    with pytest.raises(HomeAssistantError, match=exception_match):
        await hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "service",
    [SERVICE_TURN_ON, SERVICE_TURN_OFF],
)
async def test_create_program_switch_deprecation_issue(
    hass: HomeAssistant,
    appliance: HomeAppliance,
    service: str,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that we create an issue when an automation or script is using a program switch entity or the entity is used by the user."""
    entity_id = "switch.washer_program_mix"
    automation_script_issue_id = f"deprecated_program_switch_{entity_id}"
    action_handler_issue_id = f"deprecated_program_switch_{entity_id}"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {
                        "entity_id": "automation.test",
                    },
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "action": "switch.turn_on",
                            "entity_id": entity_id,
                        },
                    ],
                }
            }
        },
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 2
    assert issue_registry.async_get_issue(DOMAIN, automation_script_issue_id)
    assert issue_registry.async_get_issue(DOMAIN, action_handler_issue_id)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, automation_script_issue_id)
    assert not issue_registry.async_get_issue(DOMAIN, action_handler_issue_id)
    assert len(issue_registry.issues) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "service",
    [SERVICE_TURN_ON, SERVICE_TURN_OFF],
)
async def test_program_switch_deprecation_issue_fix(
    hass: HomeAssistant,
    appliance: HomeAppliance,
    service: str,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test we can fix the issues created when a program switch entity is in an automation or in a script or when is used."""
    entity_id = "switch.washer_program_mix"
    automation_script_issue_id = f"deprecated_program_switch_{entity_id}"
    action_handler_issue_id = f"deprecated_program_switch_{entity_id}"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {
                        "entity_id": "automation.test",
                    },
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "action": "switch.turn_on",
                            "entity_id": entity_id,
                        },
                    ],
                }
            }
        },
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 2
    assert issue_registry.async_get_issue(DOMAIN, automation_script_issue_id)
    assert issue_registry.async_get_issue(DOMAIN, action_handler_issue_id)

    for issue in issue_registry.issues.copy().values():
        _client = await hass_client()
        resp = await _client.post(
            "/api/repairs/issues/fix",
            json={"handler": DOMAIN, "issue_id": issue.issue_id},
        )
        assert resp.status == HTTPStatus.OK
        flow_id = (await resp.json())["flow_id"]
        resp = await _client.post(f"/api/repairs/issues/fix/{flow_id}")

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, automation_script_issue_id)
    assert not issue_registry.async_get_issue(DOMAIN, action_handler_issue_id)
    assert len(issue_registry.issues) == 0


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
    ("entity_id", "option_key", "appliance"),
    [
        (
            "switch.dishwasher_half_load",
            OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
            "Dishwasher",
        )
    ],
    indirect=["appliance"],
)
async def test_options_functionality(
    entity_id: str,
    option_key: OptionKey,
    appliance: HomeAppliance,
    set_active_program_options_side_effect: ActiveProgramNotSetError | None,
    set_selected_program_options_side_effect: SelectedProgramNotSetError | None,
    called_mock_method: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
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
            ProgramKey.UNKNOWN, options=[ProgramDefinitionOption(option_key, "Boolean")]
        )
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()

    assert called_mock.called
    assert called_mock.call_args.args == (appliance.ha_id,)
    assert called_mock.call_args.kwargs == {
        "option_key": option_key,
        "value": False,
    }
    assert hass.states.is_state(entity_id, STATE_OFF)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()

    assert called_mock.called
    assert called_mock.call_args.args == (appliance.ha_id,)
    assert called_mock.call_args.kwargs == {
        "option_key": option_key,
        "value": True,
    }
    assert hass.states.is_state(entity_id, STATE_ON)
