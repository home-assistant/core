"""Tests for NexBlue numbers."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

from nexblue_api import NexBlueError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import CHARGER_STATUS

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit this module's setup to the number platform."""
    with patch("homeassistant.components.nexblue.PLATFORMS", [Platform.NUMBER]):
        yield


async def test_number_entities_snapshot(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the complete NexBlue number platform through a snapshot."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        init_integration.entry_id,
    )


async def test_set_dynamic_current_limit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting the dynamic current limit."""
    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, "nexblue", "NB123456_dynamic_current_limit"
    )
    assert entity_id

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {"entity_id": entity_id, "value": 20.5},
        blocking=True,
    )

    mock_client.async_set_dynamic_current_limit.assert_awaited_once_with(
        "NB123456", 20.5
    )


async def test_set_dynamic_current_limit_requires_active_session(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting the dynamic limit requires an active charging session."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, charging_state=0
    )
    await init_integration.runtime_data.async_refresh()

    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, "nexblue", "NB123456_dynamic_current_limit"
    )
    assert entity_id
    previous_state = hass.states.get(entity_id).state

    with pytest.raises(HomeAssistantError, match="active charging session"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {"entity_id": entity_id, "value": 20.5},
            blocking=True,
        )

    mock_client.async_set_dynamic_current_limit.assert_not_awaited()
    assert hass.states.get(entity_id).state == previous_state


async def test_set_dynamic_current_limit_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rejected command retains the previously reported value."""
    mock_client.async_set_dynamic_current_limit.side_effect = NexBlueError(
        "The charger rejected the command"
    )
    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, "nexblue", "NB123456_dynamic_current_limit"
    )
    assert entity_id
    previous_state = hass.states.get(entity_id).state

    with pytest.raises(HomeAssistantError, match="rejected the command"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {"entity_id": entity_id, "value": 20.5},
            blocking=True,
        )

    mock_client.async_set_dynamic_current_limit.assert_awaited_once_with(
        "NB123456", 20.5
    )
    assert hass.states.get(entity_id).state == previous_state


async def test_number_is_unavailable_when_dynamic_limit_is_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number is unavailable when the charger lacks dynamic limit support."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, dynamic_current_limit_a=None
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, "nexblue", "NB123456_dynamic_current_limit"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_dynamic_current_limit_rounds_float_precision(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the displayed value is rounded to the supported 0.1 A step."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, dynamic_current_limit_a=7.300000190734863
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN, "nexblue", "NB123456_dynamic_current_limit"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == "7.3"
