"""Test for the SmartThings switch platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.smartthings.const import DOMAIN, MAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SWITCH)


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.2nd_floor_hallway"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", Capability.SWITCH, command, MAIN
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
@pytest.mark.parametrize(
    ("action", "argument"),
    [
        (SERVICE_TURN_ON, "on"),
        (SERVICE_TURN_OFF, "off"),
    ],
)
async def test_command_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    argument: str,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.dryer_wrinkle_prevent"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.CUSTOM_DRYER_WRINKLE_PREVENT,
        Command.SET_DRYER_WRINKLE_PREVENT,
        MAIN,
        argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ACTIVATE),
        (SERVICE_TURN_OFF, Command.DEACTIVATE),
    ],
)
async def test_custom_commands(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.refrigerator_power_cool"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7db87911-7dce-1cf2-7119-b953432a2f09",
        Capability.SAMSUNG_CE_POWER_COOL,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_ON

    await trigger_update(
        hass,
        devices,
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd",
        Capability.SWITCH,
        Attribute.SWITCH,
        "off",
    )

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_OFF


@pytest.mark.parametrize(
    ("device_fixture", "device_id", "suggested_object_id", "issue_string"),
    [
        (
            "da_ks_cooktop_31001",
            "808dbd84-f357-47e2-a0cd-3b66fa22d584",
            "induction_hob",
            "appliance",
        ),
        (
            "da_ks_microwave_0101x",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a",
            "microwave",
            "appliance",
        ),
        (
            "da_wm_dw_000001",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
            "dishwasher",
            "appliance",
        ),
        (
            "da_wm_sc_000001",
            "b93211bf-9d96-bd21-3b2f-964fcc87f5cc",
            "airdresser",
            "appliance",
        ),
        (
            "da_wm_wd_000001",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b",
            "dryer",
            "appliance",
        ),
        (
            "da_wm_wm_000001",
            "f984b91d-f250-9d42-3436-33f09a422a47",
            "washer",
            "appliance",
        ),
        (
            "hw_q80r_soundbar",
            "afcf3b91-0000-1111-2222-ddff2a0a6577",
            "soundbar",
            "media_player",
        ),
        (
            "vd_network_audio_002s",
            "0d94e5db-8501-2355-eb4f-214163702cac",
            "soundbar_living",
            "media_player",
        ),
        (
            "vd_stv_2017_k",
            "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
            "tv_samsung_8_series_49",
            "media_player",
        ),
    ],
)
async def test_create_issue_with_items(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    device_id: str,
    suggested_object_id: str,
    issue_string: str,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = f"switch.{suggested_object_id}"
    issue_id = f"deprecated_switch_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{device_id}_{MAIN}_{Capability.SWITCH}_{Attribute.SWITCH}_{Attribute.SWITCH}",
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test",
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
                            "condition": "state",
                            "entity_id": entity_id,
                            "state": "on",
                        },
                    ],
                }
            }
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state in [STATE_OFF, STATE_ON]

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == f"deprecated_switch_{issue_string}_scripts"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
        "items": "- [test](/config/automation/edit/test)\n- [test](/config/script/edit/test)",
    }

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize(
    ("device_fixture", "device_id", "suggested_object_id", "issue_string", "version"),
    [
        (
            "da_ks_cooktop_31001",
            "808dbd84-f357-47e2-a0cd-3b66fa22d584",
            "induction_hob",
            "appliance",
            "2025.10.0",
        ),
        (
            "da_ks_microwave_0101x",
            "2bad3237-4886-e699-1b90-4a51a3d55c8a",
            "microwave",
            "appliance",
            "2025.10.0",
        ),
        (
            "da_wm_dw_000001",
            "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
            "dishwasher",
            "appliance",
            "2025.10.0",
        ),
        (
            "da_wm_sc_000001",
            "b93211bf-9d96-bd21-3b2f-964fcc87f5cc",
            "airdresser",
            "appliance",
            "2025.10.0",
        ),
        (
            "da_wm_wd_000001",
            "02f7256e-8353-5bdd-547f-bd5b1647e01b",
            "dryer",
            "appliance",
            "2025.10.0",
        ),
        (
            "da_wm_wm_000001",
            "f984b91d-f250-9d42-3436-33f09a422a47",
            "washer",
            "appliance",
            "2025.10.0",
        ),
        (
            "hw_q80r_soundbar",
            "afcf3b91-0000-1111-2222-ddff2a0a6577",
            "soundbar",
            "media_player",
            "2025.10.0",
        ),
        (
            "vd_network_audio_002s",
            "0d94e5db-8501-2355-eb4f-214163702cac",
            "soundbar_living",
            "media_player",
            "2025.10.0",
        ),
        (
            "vd_stv_2017_k",
            "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
            "tv_samsung_8_series_49",
            "media_player",
            "2025.10.0",
        ),
        (
            "da_sac_ehs_000002_sub",
            "3810e5ad-5351-d9f9-12ff-000001200000",
            "warmepumpe",
            "dhw",
            "2025.12.0",
        ),
    ],
)
async def test_create_issue(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    device_id: str,
    suggested_object_id: str,
    issue_string: str,
    version: str,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = f"switch.{suggested_object_id}"
    issue_id = f"deprecated_switch_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{device_id}_{MAIN}_{Capability.SWITCH}_{Attribute.SWITCH}_{Attribute.SWITCH}",
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state in [STATE_OFF, STATE_ON]

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == f"deprecated_switch_{issue_string}"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
    }
    assert issue.breaks_in_ha_version == version

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_ON

    await trigger_health_update(
        hass, devices, "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", HealthStatus.OFFLINE
    )

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", HealthStatus.ONLINE
    )

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_UNAVAILABLE
