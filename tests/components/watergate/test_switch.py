"""Tests for the Watergate switch platform."""

from collections.abc import Generator
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException
from watergate_local_api.models import AutoShutOffState

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)

ENTITY_ID = "switch.sonic_auto_shut_off"


async def test_auto_shut_off_switch(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Toggling the switch calls the client with the requested state."""
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


async def test_switch_reflects_polled_state(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The switch reflects an auto-shut-off change picked up by polling."""
    await init_integration(hass, mock_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_watergate_client.async_get_auto_shut_off.return_value = AutoShutOffState(
        False, 1000, 60
    )
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_switch_raises_on_client_failure(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    service: str,
) -> None:
    """Client failure while toggling surfaces as a HomeAssistantError."""
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_update_auto_shut_off.side_effect = (
        WatergateApiException("boom")
    )

    with pytest.raises(HomeAssistantError, match="Failed to update auto shut-off"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
