"""Tests for NexBlue switches."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from nexblue_api import NexBlueError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nexblue.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import CHARGER_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


async def test_command_refreshes_and_assumed_state_expires(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test command refreshes run and the assumed state expires."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id
    mock_client.async_list_chargers.reset_mock()
    mock_client.async_get_charger_status.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "off"
    assert mock_client.async_list_chargers.await_count == 0
    assert mock_client.async_get_charger_status.await_count == 0

    for seconds, expected_refreshes in ((3, 1), (22, 2)):
        freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert mock_client.async_list_chargers.await_count == expected_refreshes
        assert mock_client.async_get_charger_status.await_count == expected_refreshes

    freezer.tick(timedelta(seconds=5))
    await init_integration.runtime_data.async_refresh()

    assert mock_client.async_list_chargers.await_count == 3
    assert mock_client.async_get_charger_status.await_count == 3
    assert hass.states.get(entity_id).state == "on"


async def test_new_command_replaces_pending_command_refreshes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new command replaces the previous command's refreshes."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id
    mock_client.async_list_chargers.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.async_list_chargers.await_count == 1


async def test_pending_command_refreshes_cancelled_on_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test pending command refreshes do not run after unloading the entry."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "NB123456_charging"
    )
    assert entity_id
    mock_client.async_list_chargers.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert mock_client.async_list_chargers.await_count == 0

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.async_list_chargers.await_count == 0


@pytest.mark.parametrize(
    ("charging_state", "expected_state"),
    [
        (5, "on"),
        (6, "off"),
        (7, "on"),
    ],
)
async def test_charging_session_states(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    charging_state: int,
    expected_state: str,
) -> None:
    """Test switch state reflects whether a charging session is active."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, charging_state=charging_state
    )

    await init_integration.runtime_data.async_refresh()

    assert hass.states.get("switch.nb123456_charging").state == expected_state
