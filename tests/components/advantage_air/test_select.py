"""Test the Advantage Air Select Platform."""

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config, patch_get, patch_update


@pytest.fixture
def mock_get():
    """Fixture to patch the Advantage Air async_get method."""
    with patch_get() as mock_get:
        yield mock_get


@pytest.fixture
def mock_update():
    """Fixture to patch the Advantage Air async_get method."""
    with patch_update() as mock_get:
        yield mock_get


async def test_select_async_setup_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_get, mock_update
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
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Zone 3"},
        blocking=True,
    )
    mock_update.assert_called_once()
