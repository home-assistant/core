"""Tests for sensor."""
from unittest.mock import patch

from homeassistant.components.krisinformation.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_entities_added(hass: HomeAssistant) -> None:
    """Test the entities are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title="Krisinformation",
        unique_id=123456789,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "krisinformation.crisis_alerter.CrisisAlerter.vmas",
        is_test=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("sensor")) == 1
        entity_id = hass.states.async_entity_ids("sensor")[0]

        entity_registry = er.async_get(hass)
        assert len(entity_registry.entities) == 1

        state = hass.states.get(entity_id)

        assert state is not None
        assert state.attributes["friendly_name"] == "Krisinformation test"
        assert state.attributes["icon"] == "mdi:alert"
        assert state.attributes["attribution"] == "Alerts provided by Krisinformation"
