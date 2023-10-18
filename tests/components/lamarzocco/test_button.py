"""Tests for the La Marzocco Buttons."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_start_backflush(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Drink Stats."""
    mock_lamarzocco.start_backflush.return_value = None

    state = hass.states.get("button.gs01234_start_backflush")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Start Backflush"
    assert state.attributes.get(ATTR_ICON) == "mdi:water-sync"
    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_start_backflush"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.gs01234_start_backflush",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.start_backflush.mock_calls) == 1
    mock_lamarzocco.start_backflush.assert_called_once()
