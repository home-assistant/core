"""Test the Advantage Air Update Platform."""

from homeassistant.const import STATE_ON
from homeassistant.helpers import entity_registry as er

from tests.common import load_fixture
from tests.components.advantage_air import TEST_SYSTEM_URL, add_mock_config


async def test_update_platform(hass, aioclient_mock):
    """Test update platform."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=load_fixture("advantage_air/needsUpdate.json"),
    )
    await add_mock_config(hass)

    registry = er.async_get(hass)

    entity_id = "update.testname_app"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid"
