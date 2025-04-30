"""Tests for home_connect time entities."""

from collections.abc import Awaitable, Callable
from datetime import time
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfSettings,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectApiError, HomeConnectError
import pytest

from homeassistant.components.automation import (
    DOMAIN as AUTOMATION_DOMAIN,
    automations_with_entity,
)
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN, scripts_with_entity
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, STATE_UNAVAILABLE, Platform
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
    return [Platform.TIME]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("appliance", "keys_to_check"),
    [
        (
            "Oven",
            (SettingKey.BSH_COMMON_ALARM_CLOCK,),
        )
    ],
    indirect=["appliance"],
)
async def test_connected_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    keys_to_check: tuple,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_settings_original_mock = client.get_settings

    async def get_settings_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return await get_settings_original_mock.side_effect(ha_id)

    client.get_settings = AsyncMock(side_effect=get_settings_side_effect)
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_settings = get_settings_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.TIME,
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
            Platform.TIME,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_time_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if time entities availability are based on the appliance connection state."""
    entity_ids = [
        "time.oven_alarm_clock",
    ]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            SettingKey.BSH_COMMON_ALARM_CLOCK,
        ),
    ],
)
async def test_time_entity_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    setting_key: SettingKey,
) -> None:
    """Test time entity functionality."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    value = 30
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state != value
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(second=value),
        },
    )
    await hass.async_block_till_done()
    client.set_setting.assert_awaited_once_with(
        appliance.ha_id, setting_key=setting_key, value=value
    )
    assert hass.states.is_state(entity_id, str(time(second=value)))


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{TIME_DOMAIN}.oven_alarm_clock",
            SettingKey.BSH_COMMON_ALARM_CLOCK,
            "set_setting",
        ),
    ],
)
async def test_time_entity_error(
    hass: HomeAssistant,
    client_with_exception: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    setting_key: SettingKey,
    mock_attr: str,
) -> None:
    """Test time entity error."""
    client_with_exception.get_settings.side_effect = None
    client_with_exception.get_settings.return_value = ArrayOfSettings(
        [
            GetSetting(
                key=setting_key,
                raw_key=setting_key.value,
                value=30,
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
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TIME: time(minute=1),
            },
            blocking=True,
        )
    assert getattr(client_with_exception, mock_attr).call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_create_alarm_clock_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that we create an issue when an automation or script is using a alarm clock time entity or the entity is used by the user."""
    entity_id = f"{TIME_DOMAIN}.oven_alarm_clock"
    automation_script_issue_id = (
        f"deprecated_time_alarm_clock_in_automations_scripts_{entity_id}"
    )
    action_handler_issue_id = f"deprecated_time_alarm_clock_{entity_id}"

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
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
        SCRIPT_DOMAIN,
        {
            SCRIPT_DOMAIN: {
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

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(minute=1),
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
@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_alarm_clock_deprecation_issue_fix(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test we can fix the issues created when a alarm clock time entity is in an automation or in a script or when is used."""
    entity_id = f"{TIME_DOMAIN}.oven_alarm_clock"
    automation_script_issue_id = (
        f"deprecated_time_alarm_clock_in_automations_scripts_{entity_id}"
    )
    action_handler_issue_id = f"deprecated_time_alarm_clock_{entity_id}"

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
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
        SCRIPT_DOMAIN,
        {
            SCRIPT_DOMAIN: {
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

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(minute=1),
        },
        blocking=True,
    )

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
