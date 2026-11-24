"""Test the Advantage Air Select Platform."""

from unittest.mock import AsyncMock

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test select platform."""

    await add_mock_config(hass)

    # Test MyZone Select Entity
    entity_id = "select.myzone_myzone"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Zone open with Sensor"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-myzone"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
            SelectServiceArgument.OPTION: "Zone 3",
        },
        blocking=True,
    )
    mock_update.assert_called_once()
