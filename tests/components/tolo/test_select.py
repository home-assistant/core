"""Tests for the TOLO Sauna select platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

# Entity IDs based on registration order: lamp_mode, aroma_therapy_slot
LAMP_MODE_ENTITY_ID = "select.tolo_sauna"
AROMA_THERAPY_SLOT_ENTITY_ID = "select.tolo_sauna_2"


@pytest.mark.usefixtures("init_integration")
async def test_lamp_mode_select_state(
    hass: HomeAssistant,
) -> None:
    """Test lamp mode select entity state."""
    state = hass.states.get(LAMP_MODE_ENTITY_ID)
    assert state is not None
    assert state.state == "manual"
    assert state.attributes["options"] == ["manual", "automatic"]


@pytest.mark.usefixtures("init_integration")
async def test_aroma_therapy_slot_select_state(
    hass: HomeAssistant,
) -> None:
    """Test aroma therapy slot select entity state."""
    state = hass.states.get(AROMA_THERAPY_SLOT_ENTITY_ID)
    assert state is not None
    assert state.state == "a"
    assert state.attributes["options"] == ["a", "b"]


@pytest.mark.usefixtures("init_integration")
async def test_select_lamp_mode(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test selecting a lamp mode option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: LAMP_MODE_ENTITY_ID,
            ATTR_OPTION: "automatic",
        },
        blocking=True,
    )
    mock_tolo_client.set_lamp_mode.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_select_aroma_therapy_slot(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
) -> None:
    """Test selecting an aroma therapy slot option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: AROMA_THERAPY_SLOT_ENTITY_ID,
            ATTR_OPTION: "b",
        },
        blocking=True,
    )
    mock_tolo_client.set_aroma_therapy_slot.assert_called_once()
