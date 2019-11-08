"""Define tests for the GeoNet NZ Volcano config flow."""
from datetime import timedelta

import pytest
from asynctest import patch, CoroutineMock

from homeassistant import data_entry_flow
from homeassistant.components.geonetnz_volcano import (
    config_flow,
    DOMAIN,
    FEED,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_UNIT_SYSTEM,
    CONF_SCAN_INTERVAL,
)
from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock GeoNet NZ Volcano config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
            CONF_UNIT_SYSTEM: "metric",
            CONF_SCAN_INTERVAL: 300.0,
        },
        title="-41.2, 174.7",
    )


async def test_duplicate_error(hass, config_entry):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_LATITUDE: -41.2, CONF_LONGITUDE: 174.7, CONF_RADIUS: 25}

    config_entry.add_to_hass(hass)
    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "identifier_exists"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: timedelta(minutes=4),
    }

    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: 240.0,
    }


async def test_step_user(hass):
    """Test that the user step works."""
    hass.config.latitude = -41.2
    hass.config.longitude = 174.7
    conf = {CONF_RADIUS: 25}

    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: 300.0,
    }


async def test_component_unload_config_entry(hass, config_entry):
    """Test that loading and unloading of a config entry works."""
    config_entry.add_to_hass(hass)
    with patch(
        "aio_geojson_geonetnz_volcano.GeonetnzVolcanoFeedManager.update",
        new_callable=CoroutineMock,
    ) as mock_feed_manager_update:
        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_feed_manager_update.call_count == 1
        assert hass.data[DOMAIN][FEED][config_entry.entry_id] is not None
        # Unload config entry.
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][FEED].get(config_entry.entry_id) is None
