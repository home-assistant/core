"""The tests for the demo platform."""

from collections.abc import Generator
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import geo_location
from homeassistant.components.demo import DOMAIN
from homeassistant.components.demo.geo_location import (
    DEFAULT_UPDATE_INTERVAL,
    NUMBER_OF_DEMO_DEVICES,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


@pytest.fixture
def geo_location_only() -> Generator[None]:
    """Enable only the geo_location platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.GEO_LOCATION],
    ):
        yield


@pytest.mark.usefixtures("geo_location_only")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup of demo platform via config entry."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with freeze_time(utcnow):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # In this test, one zone and geolocation entities have been
        # generated.
        all_states = [
            hass.states.get(entity_id)
            for entity_id in hass.states.async_entity_ids(geo_location.DOMAIN)
        ]
        assert len(all_states) == NUMBER_OF_DEMO_DEVICES

        for state in all_states:
            # Check a single device's attributes.
            if state.domain != geo_location.DOMAIN:
                # ignore home zone state
                continue
            assert abs(state.attributes[ATTR_LATITUDE] - hass.config.latitude) < 1.0
            assert abs(state.attributes[ATTR_LONGITUDE] - hass.config.longitude) < 1.0
            assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.KILOMETERS

        # Update (replaces 1 device).
        async_fire_time_changed(hass, utcnow + DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Get all states again, ensure that the number of states is still
        # the same, but the lists are different.
        all_states_updated = [
            hass.states.get(entity_id)
            for entity_id in hass.states.async_entity_ids(geo_location.DOMAIN)
        ]
        assert len(all_states_updated) == NUMBER_OF_DEMO_DEVICES
        assert all_states != all_states_updated


@pytest.mark.usefixtures("geo_location_only")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the config entry removes the events and stops updates."""
    utcnow = dt_util.utcnow()
    with freeze_time(utcnow):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(geo_location.DOMAIN)) == (
            NUMBER_OF_DEMO_DEVICES
        )

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.async_entity_ids(geo_location.DOMAIN) == []

        # The update timer is cancelled, so no new events are added
        async_fire_time_changed(hass, utcnow + DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.async_entity_ids(geo_location.DOMAIN) == []
