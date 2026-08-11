"""Tests for the Watergate switch platform."""

from collections.abc import Generator

import pytest
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import AsyncMock, MockConfigEntry, patch, snapshot_platform

ENTITY_ID = "switch.sonic_auto_shut_off"


async def test_auto_shut_off_switch(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Toggling the switch calls the client and updates state."""
    await init_integration(hass, mock_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_watergate_client.async_update_auto_shut_off.assert_called_once_with(
        enabled=False
    )
    assert hass.states.get(ENTITY_ID).state == "off"

    mock_watergate_client.async_update_auto_shut_off.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_watergate_client.async_update_auto_shut_off.assert_called_once_with(
        enabled=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_watergate_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
) -> None:
    """Snapshot the switch entities and their registry entries."""
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_switch_unknown_when_no_data(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Switch state is unknown when the device omits auto-shut-off data."""
    mock_watergate_client.async_get_auto_shut_off.return_value = None

    await init_integration(hass, mock_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_switch_no_rollback_on_unrelated_update(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """An unrelated coordinator update must not roll back the switch state."""
    await init_integration(hass, mock_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    coordinator = mock_entry.runtime_data
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_switch_turn_off_raises_on_client_failure(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Client failure while turning off surfaces as a HomeAssistantError."""
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_update_auto_shut_off.side_effect = (
        WatergateApiException("boom")
    )

    with pytest.raises(HomeAssistantError, match="Failed to update auto shut-off"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
