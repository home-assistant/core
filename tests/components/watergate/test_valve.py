"""Tests for the Watergate valve platform."""

from collections.abc import Generator

import pytest
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException, WatergateIndeterminateError

from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN, ValveState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_VALVE, SERVICE_OPEN_VALVE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

from tests.common import AsyncMock, MockConfigEntry


async def test_change_valve_state_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable after failed update."""
    await init_integration(hass, mock_entry)

    entity_id = "valve.sonic"

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.OPEN
    assert registered_entity == snapshot


async def test_change_valve_state(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable after failed update."""
    await init_integration(hass, mock_entry)

    entity_id = "valve.sonic"

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.OPEN

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.CLOSING

    mock_watergate_client.async_set_valve_state.assert_called_once_with("closed")
    mock_watergate_client.async_set_valve_state.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.OPENING

    mock_watergate_client.async_set_valve_state.assert_called_once_with("open")


@pytest.mark.parametrize("service", [SERVICE_OPEN_VALVE, SERVICE_CLOSE_VALVE])
@pytest.mark.parametrize(
    "exception", [WatergateApiException, WatergateIndeterminateError]
)
async def test_valve_action_failure(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    service: str,
    exception: type[WatergateApiException],
) -> None:
    """Test a failing valve action raises a translated HomeAssistantError."""
    await init_integration(hass, mock_entry)

    entity_id = "valve.sonic"
    mock_watergate_client.async_set_valve_state.side_effect = exception("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            VALVE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "valve_action_failed"

    # The state must not be changed optimistically when the request fails
    state = hass.states.get(entity_id)
    assert state
    assert state.state == ValveState.OPEN
