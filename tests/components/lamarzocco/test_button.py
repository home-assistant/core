"""Tests for the La Marzocco Buttons."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylamarzocco.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_start_backflush(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco backflush button."""

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"button.{serial_number}_start_backflush")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    with patch(
        "homeassistant.components.lamarzocco.button.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: f"button.{serial_number}_start_backflush",
            },
            blocking=True,
        )

    assert len(mock_lamarzocco.start_backflush.mock_calls) == 1
    mock_lamarzocco.start_backflush.assert_called_once()


async def test_button_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco button error."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"button.{serial_number}_start_backflush")
    assert state

    mock_lamarzocco.start_backflush.side_effect = RequestNotSuccessful("Boom.")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: f"button.{serial_number}_start_backflush",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "button_error"
