"""Test Satel Integra switch."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_CODE, MOCK_ENTRY_ID, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def switches_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("mock_satel")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test switch correctly being set up."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    await snapshot_platform(hass, entity_registry, snapshot, MOCK_ENTRY_ID)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "1234567890_switch_1")}
    )

    assert device_entry == snapshot(name="device")


async def test_switch_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch has a correct initial state ON after initialization."""
    mock_satel.violated_outputs = [1]

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_ON


async def test_switch_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    monitor_status_call = mock_satel.monitor_status.call_args_list[0][0]
    output_update_method = monitor_status_call[2]

    # Should do nothing, only react to it's own number
    output_update_method({"outputs": {2: 1}})
    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    output_update_method({"outputs": {1: 1}})
    assert hass.states.get("switch.switchable_output").state == STATE_ON


async def test_switch_change_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Test turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )

    assert hass.states.get("switch.switchable_output").state == STATE_ON
    mock_satel.set_output.assert_awaited_once_with(MOCK_CODE, 1, True)

    mock_satel.set_output.reset_mock()

    # Test turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )

    assert hass.states.get("switch.switchable_output").state == STATE_OFF
    mock_satel.set_output.assert_awaited_once_with(MOCK_CODE, 1, False)
