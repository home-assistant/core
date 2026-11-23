"""Tests for the ESI R2D7 cover platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockConnection

CHANNEL_1 = "cover.esi_r2d7_system_1_channel_01"
CHANNEL_2 = "cover.esi_r2d7_system_1_channel_02"
CHANNEL_3 = "cover.esi_r2d7_system_1_channel_03"


async def _call(hass: HomeAssistant, service: str, entity_id: str) -> None:
    """Call a cover action and wait for it."""
    await hass.services.async_call(
        COVER_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test one blind per channel, on one device, with unknown state."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    assert sorted(entry.entity_id for entry in entries) == [
        CHANNEL_1,
        CHANNEL_2,
        CHANNEL_3,
    ]
    assert entity_registry.async_get(CHANNEL_1).unique_id == (
        f"{init_integration.entry_id}_1"
    )

    state = hass.states.get(CHANNEL_1)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == "blind"
    assert state.attributes[ATTR_ASSUMED_STATE] is True
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    device = device_registry.async_get(entries[0].device_id)
    assert device.manufacturer == "ESI"
    assert device.model == "R2D7"
    assert device.name == "ESI R2D7 system 1"


async def test_open_and_close(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test Open and Close address the channel and set the assumed state."""
    await _call(hass, SERVICE_OPEN_COVER, CHANNEL_2)
    mock_connection.open_blind.assert_awaited_once_with(2)
    assert hass.states.get(CHANNEL_2).state == CoverState.OPEN

    await _call(hass, SERVICE_CLOSE_COVER, CHANNEL_2)
    mock_connection.close_blind.assert_awaited_once_with(2)
    assert hass.states.get(CHANNEL_2).state == CoverState.CLOSED


async def test_stop_marks_recently_moved_blinds_unknown(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a Stop is system-wide and clears the state of blinds it may have caught."""
    for entity_id in (CHANNEL_1, CHANNEL_2, CHANNEL_3):
        await _call(hass, SERVICE_CLOSE_COVER, entity_id)
    mock_connection.recently_moved = {2}

    await _call(hass, SERVICE_STOP_COVER, CHANNEL_1)

    mock_connection.stop_system.assert_awaited_once_with()
    assert hass.states.get(CHANNEL_1).state == STATE_UNKNOWN
    assert hass.states.get(CHANNEL_2).state == STATE_UNKNOWN
    assert hass.states.get(CHANNEL_3).state == CoverState.CLOSED


@pytest.mark.parametrize(
    ("service", "method", "first_service", "expected_state"),
    [
        (SERVICE_OPEN_COVER, "open_blind", SERVICE_CLOSE_COVER, CoverState.CLOSED),
        (SERVICE_CLOSE_COVER, "close_blind", SERVICE_OPEN_COVER, CoverState.OPEN),
        (SERVICE_STOP_COVER, "stop_system", SERVICE_CLOSE_COVER, CoverState.CLOSED),
    ],
)
@pytest.mark.parametrize(
    "exception", [OSError("link gone"), HomeAssistantError("proxy not ready")]
)
async def test_command_error(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
    service: str,
    method: str,
    first_service: str,
    expected_state: str,
    exception: Exception,
) -> None:
    """Test a failed write raises and keeps the previous state."""
    await _call(hass, first_service, CHANNEL_1)
    getattr(mock_connection, method).side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, service, CHANNEL_1)

    assert exc_info.value.translation_key == "command_failed"
    assert hass.states.get(CHANNEL_1).state == expected_state


async def test_unavailable_when_link_drops(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test the blinds follow the serial link."""
    # Keep the entry loaded so the entity state can be seen.
    with patch.object(hass.config_entries, "async_schedule_reload"):
        mock_connection.mock_link(False)

    assert hass.states.get(CHANNEL_1).state == STATE_UNAVAILABLE

    mock_connection.mock_link(True)

    assert hass.states.get(CHANNEL_1).state == STATE_UNKNOWN
