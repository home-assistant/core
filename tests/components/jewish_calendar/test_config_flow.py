"""Test the Jewish calendar config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.jewish_calendar import config_flow
from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_DIASPORA,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_step_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"name": "Jewish Calendar", "diaspora": True, "language": "hebrew"},
    )

    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jewish Calendar"
    assert result["data"] == {
        "name": "Jewish Calendar",
        "diaspora": True,
        "language": "hebrew",
    }


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
