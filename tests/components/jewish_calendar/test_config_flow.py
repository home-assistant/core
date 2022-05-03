"""Test the Jewish calendar config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.jewish_calendar import config_flow
from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    CONF_LANGUAGE,
    DEFAULT_DIASPORA,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

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
        "homeassistant.components.jewish_calendar.config_flow.validate_input",
        return_value=mock_coro({"title": "Test Title"}),
    ), patch(
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
    assert result2["title"] == "Test Title"
    assert result2["data"] == {
        "name": "JCalendar",
        "diaspora": True,
        "language": "hebrew",
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("diaspora", [True, False])
@pytest.mark.parametrize("language", ["hebrew", "english"])
async def test_step_import_no_options(hass, language, diaspora):
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
    }


async def test_step_import_with_options(hass):
    """Test that the import step works."""
    conf = {
        DOMAIN: {
            CONF_NAME: "test",
            CONF_DIASPORA: DEFAULT_DIASPORA,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
            CONF_CANDLE_LIGHT_MINUTES: 20,
            CONF_HAVDALAH_OFFSET_MINUTES: 50,
            CONF_LATITUDE: 31.76,
            CONF_LONGITUDE: 35.235,
        }
    }

    flow = config_flow.JewishCalendarConfigFlow()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf[DOMAIN])
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == {
        CONF_NAME: "test",
        CONF_DIASPORA: DEFAULT_DIASPORA,
        CONF_LANGUAGE: DEFAULT_LANGUAGE,
        CONF_CANDLE_LIGHT_MINUTES: 20,
        CONF_HAVDALAH_OFFSET_MINUTES: 50,
        CONF_LATITUDE: 31.76,
        CONF_LONGITUDE: 35.235,
    }
