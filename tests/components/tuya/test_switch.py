"""Test Tuya switch platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tuya import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("preexisting_entity", "disabled_by", "expected_entity", "expected_issue"),
    [
        (True, None, True, True),
        (True, er.RegistryEntryDisabler.USER, False, False),
        (False, None, False, False),
    ],
)
@pytest.mark.parametrize(
    "mock_device_code",
    ["sfkzq_rzklytdei8i8vo37"],
)
async def test_sfkzq_deprecated_switch(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    preexisting_entity: bool,
    disabled_by: er.RegistryEntryDisabler,
    expected_entity: bool,
    expected_issue: bool,
) -> None:
    """Test switch deprecation issue."""
    original_entity_id = "switch.balkonbewasserung_switch"
    entity_unique_id = "tuya.73ov8i8iedtylkzrqzkfsswitch"
    if preexisting_entity:
        suggested_id = original_entity_id.replace(f"{SWITCH_DOMAIN}.", "")
        entity_registry.async_get_or_create(
            SWITCH_DOMAIN,
            DOMAIN,
            entity_unique_id,
            suggested_object_id=suggested_id,
            disabled_by=disabled_by,
        )

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert (
        entity_registry.async_get(original_entity_id) is not None
    ) is expected_entity
    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{entity_unique_id}",
        )
        is not None
    ) is expected_issue


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
@pytest.mark.parametrize(
    "mock_device_code",
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("service", "expected_commands"),
    [
        (
            SERVICE_TURN_ON,
            [{"code": "switch", "value": True}],
        ),
        (
            SERVICE_TURN_OFF,
            [{"code": "switch", "value": False}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test switch action."""
    entity_id = "switch.din_socket"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, expected_commands
    )


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
@pytest.mark.parametrize(
    "mock_device_code",
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("initial_status", "expected_state"),
    [
        (True, "on"),
        (False, "off"),
        (None, STATE_UNKNOWN),
        ("some string", STATE_UNKNOWN),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    initial_status: Any,
    expected_state: str,
) -> None:
    """Test switch state."""
    entity_id = "switch.din_socket"
    mock_device.status["switch"] = initial_status
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
