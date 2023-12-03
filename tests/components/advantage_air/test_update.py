"""Test the Advantage Air Update Platform."""
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config


async def test_update_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update platform."""

    await add_mock_config(hass)

    entity_id = "update.testname_app"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid"
