"""Test Tuya switch platform."""

import re
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
import requests
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.exceptions import ApiRequestException

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("no_quirk")
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


@pytest.mark.usefixtures("no_quirk")
@pytest.mark.parametrize("mock_device_code", ["kg_zqq3cipq"])
async def test_rcu_switches(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The RCU exposes a master switch and sixteen correctly numbered channels."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("no_quirk")
@pytest.mark.parametrize("mock_device_code", ["kg_zqq3cipq"])
@pytest.mark.parametrize(
    "code", ["switch_1", *(f"switch_{index}" for index in range(7, 23))]
)
@pytest.mark.parametrize(
    ("service", "value"),
    [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)],
)
async def test_rcu_switch_commands(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    code: str,
    service: str,
    value: bool,
) -> None:
    """Physical channel labels must not change the DP code sent to the device."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "tuya", f"tuya.{mock_device.id}{code}"
    )
    assert entity_id is not None

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": code, "value": value}]
    )


@pytest.mark.usefixtures("no_quirk")
@pytest.mark.parametrize("mock_device_code", ["kg_zqq3cipq"])
@pytest.mark.parametrize(
    "code", ["switch_1", *(f"switch_{index}" for index in range(7, 23))]
)
async def test_rcu_switch_reports(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    entity_registry: er.EntityRegistry,
    code: str,
) -> None:
    """Reports update only the corresponding physical channel."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "tuya", f"tuya.{mock_device.id}{code}"
    )
    assert entity_id is not None

    await notification_helper.async_send_device_update(mock_device, {code: True})

    assert {
        state.entity_id
        for state in hass.states.async_all(SWITCH_DOMAIN)
        if state.state == "on"
    } == {entity_id}


@pytest.mark.usefixtures("no_quirk")
@pytest.mark.parametrize("mock_device_code", ["kg_zqq3cipq"])
async def test_other_kg_products_keep_category_switches(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """The RCU override does not affect another product with the same DP codes."""
    mock_device.product_id = "another_product"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == {
        f"tuya.{mock_device.id}switch_1",
        f"tuya.{mock_device.id}switch_7",
        f"tuya.{mock_device.id}switch_8",
    }


@pytest.mark.parametrize(
    "mock_device_code",
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays
        # at available_reported
        ({"countdown_1": 50}, "off", "2024-01-01T00:00:20+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"switch": True}, "on", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"countdown_1": 50, "switch": True},
            "on",
            "2024-01-01T00:01:00+00:00",
        ),
    ],
)
@pytest.mark.freeze_time("2024-01-01")
async def test_selective_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
    updates: dict[str, Any],
    expected_state: str,
    last_reported: str,
) -> None:
    """Test skip_update/last_reported."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await check_selective_state_update(
        hass,
        mock_device,
        notification_helper,
        freezer,
        entity_id="switch.din_socket",
        dpcode="switch",
        initial_state="off",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


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


@pytest.mark.usefixtures("no_quirk")
@pytest.mark.parametrize("mock_device_code", ["cz_PGEkBctAbtzKOZng"])
@pytest.mark.parametrize(
    ("side_effect", "expected_message"),
    [
        pytest.param(
            ApiRequestException(error_code="-9999999", error_message="sign invalid"),
            "The Tuya cloud rejected the command",
            id="rejected",
        ),
        pytest.param(
            requests.exceptions.ConnectionError,
            "Failed to send the command to the Tuya cloud",
            id="connection_error",
        ),
        pytest.param(
            requests.exceptions.Timeout,
            "Failed to send the command to the Tuya cloud",
            id="timeout",
        ),
    ],
)
async def test_action_error(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    side_effect: Exception,
    expected_message: str,
) -> None:
    """Test errors while sending a command are raised as Home Assistant errors."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=re.escape(expected_message)):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.din_socket"},
            blocking=True,
        )


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


@pytest.mark.parametrize("mock_device_code", ["hwsb_ircs2n82vgrozoew"])
async def test_hwsb_switch_with_quirk(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test HWSB outdoor equipment switch with quirk applied."""
    mock_device.status["switch"] = True
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    entity_id = "switch.inverflow"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "switch", "value": False}]
    )
