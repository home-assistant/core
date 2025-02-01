"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfSettings,
    Event,
    EventKey,
    EventMessage,
    GetSetting,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.event import ArrayOfEvents, EventType
from aiohomeconnect.model.program import ArrayOfPrograms, EnumerateProgram
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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


async def test_switches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test switch entities."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    (
        "entity_id",
        "service",
        "settings_key_arg",
        "setting_value_arg",
        "state",
        "appliance_ha_id",
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
    indirect=["appliance_ha_id"],
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
    setup_credentials: None,
    appliance_ha_id: str,
    client: MagicMock,
) -> None:
    """Test switch functionality."""

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id})
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance_ha_id, setting_key=settings_key_arg, value=setting_value_arg
    )
    assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize(
    ("entity_id", "program_key", "appliance_ha_id"),
    [
        (
            "switch.dryer_program_mix",
            ProgramKey.LAUNDRY_CARE_DRYER_MIX,
            "Dryer",
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_program_switch_functionality(
    entity_id: str,
    program_key: ProgramKey,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    appliance_ha_id: str,
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

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_ON)
    client.start_program.assert_awaited_once_with(
        appliance_ha_id, program_key=program_key
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, STATE_OFF)
    client.stop_program.assert_awaited_once_with(appliance_ha_id)


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
    ("entity_id", "status", "service", "state", "appliance_ha_id"),
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
    indirect=["appliance_ha_id"],
)
async def test_ent_desc_switch_functionality(
    entity_id: str,
    status: dict,
    service: str,
    state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    appliance_ha_id: str,
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
        "appliance_ha_id",
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
    indirect=["appliance_ha_id"],
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
    setup_credentials: None,
    appliance_ha_id: str,
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
        "appliance_ha_id",
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
    indirect=["appliance_ha_id"],
)
async def test_power_swtich(
    entity_id: str,
    allowed_values: list[str | None] | None,
    service: str,
    setting_value_arg: str,
    power_state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    appliance_ha_id: str,
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
        appliance_ha_id,
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
    setup_credentials: None,
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
    setup_credentials: None,
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
async def test_create_issue(
    hass: HomeAssistant,
    appliance_ha_id: str,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = "switch.washer_program_mix"
    issue_id = f"deprecated_program_switch_{entity_id}"

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

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0
