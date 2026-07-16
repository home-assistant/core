"""Tests for the Solyx Energy select platform."""

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.solyx_energy.api import SolyxEnergyWriteError
from homeassistant.components.solyx_energy.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.exceptions import HomeAssistantError

from .const import NYMO_DEVICE_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import EntityRegistry


async def test_select_state_and_write(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_solyx_api_client,
    init_integration,
) -> None:
    """Test the select entity state, options, and write path."""
    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, f"{NYMO_DEVICE_ID}-operatingMode"
    )
    assert entity_id is not None

    # Validate the selected option, and the list of available options.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "direct"
    assert state.attributes["options"] == ["direct", "muted"]

    # Pick a new option and check if it is sent to the (mock) API.
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "muted"},
        blocking=True,
    )
    mock_solyx_api_client.async_set_asset_attribute.assert_called_once_with(
        NYMO_DEVICE_ID,
        "operatingMode",
        "MUTED",
    )
    # The state should have updated to the new option.
    new_state = hass.states.get(entity_id)
    assert new_state is not None
    assert new_state.state == "muted"


async def test_select_api_failure(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_solyx_api_client,
    init_integration,
) -> None:
    """Test that an API error (SolyxEnergyWriteError) during a write raises HomeAssistantError."""
    mock_solyx_api_client.async_set_asset_attribute.side_effect = SolyxEnergyWriteError
    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, f"{NYMO_DEVICE_ID}-operatingMode"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "muted"},
            blocking=True,
        )
