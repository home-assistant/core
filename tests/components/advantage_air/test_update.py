"""Test the Advantage Air Update Platform."""
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config, patch_get

from tests.common import load_json_object_fixture

TEST_SYSTEM_DATA = load_json_object_fixture("needsUpdate.json", DOMAIN)


async def test_update_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update platform."""

    with patch_get(return_value=TEST_SYSTEM_DATA):
        await add_mock_config(hass)

        entity_id = "update.testname_app"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON

        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == "uniqueid"
