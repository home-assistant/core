"""Test Tewke button."""

from unittest.mock import AsyncMock

import pytest
from pytewke.data import ConfigData
from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidRequestError,
    PyTewkeUnknownError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tap_with_button(mock_tap):
    """Mock tap with button data."""
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData.model_construct(
            hardware_id="hw123",
            device_name="My Tap",
        )
    )
    mock_tap.restart = AsyncMock()
    return mock_tap


async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_button,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and pressing of the Tewke button."""
    mock_config_entry.add_to_hass(hass)

    # Enable disabled entity BEFORE setting up the entry
    entity_registry.async_get_or_create(
        "button",
        "tewke",
        "hw123_restart",
        suggested_object_id="living_room_tewke_switch_restart",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    button_entities = [ent for ent in entities if ent.domain == "button"]

    assert len(button_entities) == 1

    entity_entry = button_entities[0]
    assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state == snapshot(name=f"{entity_entry.entity_id}-state")

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )

    mock_tap_with_button.restart.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (
            PyTewkeInvalidRequestError("Invalid request"),
            "Internal error restarting Tewke Tap Panel",
        ),
        (
            RuntimeError("Runtime error"),
            "Internal error restarting Tewke Tap Panel",
        ),
        (
            PyTewkeCoapError("Coap error", code=1),
            "Error restarting Tewke Tap Panel",
        ),
        (
            PyTewkeUnknownError("Unknown error"),
            "Error restarting Tewke Tap Panel",
        ),
        (
            TimeoutError("Timeout error"),
            "Error restarting Tewke Tap Panel",
        ),
    ],
)
async def test_button_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_button,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_message: str,
) -> None:
    """Test error handling when pressing the button."""
    mock_config_entry.add_to_hass(hass)

    # Enable disabled entity BEFORE setting up the entry
    entity_registry.async_get_or_create(
        "button",
        "tewke",
        "hw123_restart",
        suggested_object_id="living_room_tewke_switch_restart",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tap_with_button.restart.side_effect = exception

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.living_room_tewke_switch_restart"},
            blocking=True,
        )
