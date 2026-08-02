"""Tests for Redfish power switches."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.redfish.coordinator import RedfishError
from homeassistant.components.redfish.models import RedfishData
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_power_state_and_unique_ids(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test state is on only for exact Redfish On and IDs are stable."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "uuid-1_power"
    )
    fallback_entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "redfish-entry_2_power"
    )
    assert entity_id is not None
    assert fallback_entity_id is not None
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"
    assert (fallback_state := hass.states.get(fallback_entity_id))
    assert fallback_state.state == "off"

    coordinator = init_integration.runtime_data
    system = coordinator.data.systems["1"]
    coordinator.async_set_updated_data(
        RedfishData(
            systems={
                **coordinator.data.systems,
                "1": replace(system, power_state="PoweringOn"),
            }
        )
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "off"


async def test_primary_power_actions(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switches use only On and GracefulShutdown at the advertised target."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "uuid-1_power"
    )
    assert entity_id is not None
    reset = mock_redfish_api[1]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reset.assert_awaited_once_with(
        "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", "GracefulShutdown"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"

    reset.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reset.assert_awaited_once_with(
        "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", "On"
    )


async def test_unsupported_primary_power_action(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unsupported power actions do not issue a reset request."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "redfish-entry_2_power"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    mock_redfish_api[1].assert_not_awaited()


async def test_power_action_error_is_translated(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reset communication errors expose a translated message."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "uuid-1_power"
    )
    assert entity_id is not None
    mock_redfish_api[1].side_effect = RedfishError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_domain == "redfish"
    assert exc_info.value.translation_key == "reset_failed"


async def test_system_is_unavailable_when_missing_from_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a missing system is unavailable without property errors."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "redfish", "uuid-1_power"
    )
    assert entity_id is not None
    coordinator = init_integration.runtime_data

    coordinator.async_set_updated_data(
        RedfishData(systems={"2": coordinator.data.systems["2"]})
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "unavailable"
