"""Test Lutron switch platform."""

from unittest.mock import MagicMock, patch

from pylutron import Led
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms():
    """Patch PLATFORMS for all tests in this file."""
    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_switch_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch setup."""
    mock_config_entry.add_to_hass(hass)

    switch = mock_lutron.areas[0].outputs[1]
    switch.level = 0
    switch.last_level.return_value = 0

    led = mock_lutron.areas[0].keypads[0].leds[0]
    led.state = 0
    led.last_state = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify a repair issue was created
    issue = issue_registry.async_get_issue("lutron", "deprecated_led_switch")
    assert issue is not None
    assert issue.translation_key == "deprecated_led_switch"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_switch_turn_on_off(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch turn on and off."""
    mock_config_entry.add_to_hass(hass)

    switch = mock_lutron.areas[0].outputs[1]
    switch.level = 0
    switch.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.test_switch"

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert switch.level == 100

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert switch.level == 0


async def test_led_turn_on_off(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test LED turn on and off."""
    mock_config_entry.add_to_hass(hass)

    led = mock_lutron.areas[0].keypads[0].leds[0]
    led.state = Led.LED_OFF
    led.last_state = Led.LED_OFF

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.test_keypad_test_button"

    # Verify hidden by default
    entry = entity_registry.async_get(entity_id)
    assert entry.hidden_by == er.RegistryEntryHider.INTEGRATION

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert led.state == Led.LED_ON

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert led.state == Led.LED_OFF
