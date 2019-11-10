"""Test the Jewish calendar config flow."""
import pytest
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.jewish_calendar.const import (
    CONF_DIASPORA,
    CONF_LANGUAGE,
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DOMAIN,
)
from homeassistant.components.jewish_calendar import config_flow
from homeassistant.const import CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import mock_coro


async def test_step_user(hass):
    """Test user config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jewish_calendar.async_setup",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.jewish_calendar.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "JCalendar", "diaspora": True, "language": "hebrew"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "JCalendar"
    assert result2["data"] == {
        "name": "JCalendar",
        "diaspora": True,
        "language": "hebrew",
        "candle_lighting_minutes_before_sunset": 18,
        "havdalah_minutes_after_sunset": 0,
        "latitude": 32.87336,
        "longitude": -117.22743,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("diaspora", [True, False])
@pytest.mark.parametrize("language", ["hebrew", "english"])
async def test_step_import(hass, language, diaspora):
    """Test that the import step works."""
    conf = {
        DOMAIN: {CONF_NAME: "test", CONF_LANGUAGE: language, CONF_DIASPORA: diaspora}
    }

    flow = config_flow.JewishCalendarConfigFlow()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf[DOMAIN])
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == {
        CONF_NAME: "test",
        CONF_LANGUAGE: language,
        CONF_DIASPORA: diaspora,
        CONF_CANDLE_LIGHT_MINUTES: DEFAULT_CANDLE_LIGHT,
        CONF_HAVDALAH_OFFSET_MINUTES: DEFAULT_HAVDALAH_OFFSET_MINUTES,
        CONF_LATITUDE: 32.87336,
        CONF_LONGITUDE: -117.22743,
    }
