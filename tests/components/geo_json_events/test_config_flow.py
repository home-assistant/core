"""Define tests for the GeoJSON Events config flow."""
from datetime import timedelta

import pytest

from homeassistant import config_entries
from homeassistant.components.geo_json_events import DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.geo_json_events.conftest import URL

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_duplicate_error_user(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: URL,
            CONF_LOCATION: {
                CONF_LATITUDE: -41.2,
                CONF_LONGITUDE: 174.7,
                CONF_RADIUS: 25.0,
            },
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_error_import(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_URL: URL,
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_step_import(hass: HomeAssistant) -> None:
    """Test that the import step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_URL: URL,
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
            # This custom scan interval will not be carried over into the configuration.
            CONF_SCAN_INTERVAL: timedelta(minutes=4),
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"] == "http://geo.json.local/geo_json_events.json (-41.2, 174.7)"
    )
    assert result["data"] == {
        CONF_URL: URL,
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
    }


async def test_step_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: URL,
            CONF_LOCATION: {
                CONF_LATITUDE: -41.2,
                CONF_LONGITUDE: 174.7,
                CONF_RADIUS: 25000.0,
            },
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"] == "http://geo.json.local/geo_json_events.json (-41.2, 174.7)"
    )
    assert result["data"] == {
        CONF_URL: URL,
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25.0,
    }
