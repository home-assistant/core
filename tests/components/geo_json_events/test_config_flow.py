"""Define tests for the GeoJSON Events config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.geo_json_events import DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.geo_json_events.conftest import URL

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_duplicate_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_URL: URL, CONF_LATITUDE: -41.2, CONF_LONGITUDE: 174.7, CONF_RADIUS: 25}
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_step_import(hass: HomeAssistant) -> None:
    """Test that the import step works."""
    conf = {
        CONF_URL: URL,
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: 240,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "http://geo.json.local/geo_json_events.json, -41.2, 174.7"
    assert result["data"] == {
        CONF_URL: URL,
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: 240.0,
    }


async def test_step_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    hass.config.latitude = -41.2
    hass.config.longitude = 174.7
    conf = {CONF_URL: URL, CONF_RADIUS: 25}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "http://geo.json.local/geo_json_events.json, -41.2, 174.7"
    assert result["data"] == {
        CONF_URL: URL,
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: 300.0,
    }
