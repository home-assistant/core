"""Tests for the Besen switch platform."""

from unittest.mock import AsyncMock, Mock

from besen.exceptions import CommandFailed
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.besen.const import DOMAIN
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import publish_besen_state
from .conftest import charger_state, setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "switch.garage_charge"


async def test_switch_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test switch entity state and registry data."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_besen_client.async_start.assert_awaited_once()


async def test_switch_updates_from_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test switch state updates from client push data."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    publish_besen_state(mock_besen_client, charger_state(charger_status=False))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_updates_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test switch state updates when the coordinator refreshes."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    mock_besen_client.state = charger_state(charger_status=False)
    await async_update_entity(hass, ENTITY_ID)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("available", "authenticated"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_switch_unavailable_from_client_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    available: bool,
    authenticated: bool,
) -> None:
    """Test switch availability follows client availability and authentication."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    publish_besen_state(
        mock_besen_client,
        charger_state(available=available, authenticated=authenticated),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_switch_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test switch turn on and turn off services."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    mock_besen_client.async_stop_charging.assert_awaited_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    mock_besen_client.async_start_charging.assert_awaited_once()


async def test_switch_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test command failures are translated to Home Assistant errors."""

    mock_besen_client.async_start_charging = AsyncMock(
        side_effect=CommandFailed("failed")
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
