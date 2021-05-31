"""Tests for Islamic Prayer Times config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components import islamic_prayer_times
from homeassistant.components.islamic_prayer_times.const import (
    CONF_ASR_TUNE,
    CONF_CALC_METHOD,
    CONF_FARJ_TUNE,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    CONF_TUNE,
    DOMAIN,
)

from tests.common import MockConfigEntry

MOCK_OPTIONS = {
    CONF_CALC_METHOD: "ISNA",
    CONF_SCHOOL: "Shafi",
    CONF_LAT_ADJ_METHOD: "Middle of the Night",
    CONF_MIDNIGHT_MODE: "Standard",
}
MOCK_TUNE_OPTIONS = {CONF_FARJ_TUNE: 3, CONF_ASR_TUNE: -2}


async def test_flow_works(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Islamic Prayer Times"


async def test_options(hass):
    """Test updating options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Islamic Prayer Times",
        data={},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert not result["last_step"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=MOCK_OPTIONS
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "set_times_tune"
    assert result["last_step"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=MOCK_TUNE_OPTIONS
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_CALC_METHOD: "ISNA",
        CONF_SCHOOL: "Shafi",
        CONF_LAT_ADJ_METHOD: "Middle of the Night",
        CONF_MIDNIGHT_MODE: "Standard",
        CONF_TUNE: {CONF_FARJ_TUNE: 3, CONF_ASR_TUNE: -2},
    }


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
