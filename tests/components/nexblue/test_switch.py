"""Tests for NexBlue switches."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from nexblue_api import NexBlueError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nexblue.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit this module's setup to the switch platform."""
    with patch("homeassistant.components.nexblue.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_switch_entities_snapshot(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the complete NexBlue switch platform through a snapshot."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        init_integration.entry_id,
    )


async def test_charger_removed_from_list_becomes_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a charger missing from a refresh does not raise an exception."""
    mock_client.async_list_chargers.return_value = []

    await init_integration.runtime_data.async_refresh()

    assert hass.states.get("switch.nb123456_charging").state == STATE_UNAVAILABLE


async def test_turn_on_starts_charging(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on sends the start command and updates the state."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_client.async_start_charging.assert_awaited_once_with("NB123456")
    assert hass.states.get(entity_id).state == "on"


async def test_turn_off_stops_charging(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning off sends the stop command and updates the state."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_client.async_stop_charging.assert_awaited_once_with("NB123456")
    assert hass.states.get(entity_id).state == "off"


async def test_command_error_is_reported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rejected command is reported as a Home Assistant error."""
    mock_client.async_start_charging.side_effect = NexBlueError(
        "The charger rejected the command"
    )

    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id

    with pytest.raises(HomeAssistantError, match="rejected the command"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
