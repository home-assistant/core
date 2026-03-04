"""Tests for the Hidromotic switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.hidromotic.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up switch platform."""
    return [Platform.SWITCH]


async def test_zone_switches_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that zone switches are created."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check zone switches exist
    state = hass.states.get("switch.chi_smart_192_168_1_250_zone_1")
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get("switch.chi_smart_192_168_1_250_zone_2")
    assert state is not None
    assert state.state == STATE_OFF


async def test_auto_riego_switch_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that auto riego switch is created."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Find entity by unique_id using entity registry
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{config_entry.entry_id}_auto_riego"
    )
    assert entity_entry is not None

    state = hass.states.get(entity_entry)
    assert state is not None
    assert state.state == STATE_ON


async def test_zone_switch_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test turning on a zone switch."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.chi_smart_192_168_1_250_zone_1"},
        blocking=True,
    )

    mock_client.set_zone_state.assert_called_once_with(0, True)


async def test_zone_switch_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test turning off a zone switch."""
    config_entry.add_to_hass(hass)

    # Set zone to on initially
    mock_client.is_zone_on.return_value = True
    mock_client.data["zones"][0]["estado"] = 1

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.chi_smart_192_168_1_250_zone_1"},
        blocking=True,
    )

    mock_client.set_zone_state.assert_called_once_with(0, False)


async def test_auto_riego_switch_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test turning off auto riego."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Find entity by unique_id using entity registry
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{config_entry.entry_id}_auto_riego"
    )
    assert entity_id is not None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_auto_riego.assert_called_once_with(False)


async def test_auto_riego_switch_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test turning on auto riego."""
    config_entry.add_to_hass(hass)

    # Set auto riego to off initially
    mock_client.is_auto_riego_on.return_value = False

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Find entity by unique_id using entity registry
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{config_entry.entry_id}_auto_riego"
    )
    assert entity_id is not None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_auto_riego.assert_called_once_with(True)


async def test_zone_switch_extra_attributes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test zone switch extra state attributes."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.chi_smart_192_168_1_250_zone_1")
    assert state is not None
    assert state.attributes.get("duration_minutes") == 30
    assert state.attributes.get("slot_id") == 0
