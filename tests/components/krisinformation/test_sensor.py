"""Tests for sensor."""
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.krisinformation import generate_mock_event
from homeassistant.components.krisinformation.const import DOMAIN
from homeassistant.components.krisinformation.sensor import MIN_TIME_BETWEEN_UPDATES
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_entities_added(hass: HomeAssistant) -> None:
    """Test the entities are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title="Krisinformation",
        unique_id=123456789,
    )
    config_entry.add_to_hass(hass)

    utcnow = dt_util.utcnow()
    with freeze_time(utcnow), patch(
        "krisinformation.crisis_alerter.CrisisAlerter.vmas",
        is_test=True,
    ) as mock_vma:
        mock_vma.return_value = [generate_mock_event("Test-VMA-1337-1", "Test VMA 1")]

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("sensor")) == 1
        entity_id = hass.states.async_entity_ids("sensor")[0]

        entity_registry = er.async_get(hass)
        assert len(entity_registry.entities) == 1

        async_fire_time_changed(hass, utcnow + MIN_TIME_BETWEEN_UPDATES)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)

        assert state is not None
        assert state.attributes["friendly_name"] == "Krisinformation test"
        assert state.attributes["icon"] == "mdi:alert"
        assert state.attributes["attribution"] == "Alerts provided by Krisinformation"
