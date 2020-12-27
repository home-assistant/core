"""The tests config_flow for time_date component."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.time_date.const import DOMAIN

MOCK_IMPORT = {
    "display_options": [
        "time",
        "date",
        "date_time",
        "date_time_utc",
        "date_time_iso",
        "time_date",
        "time_utc",
        "beat",
    ]
}


async def test_form_import(hass):
    """Test we get the form with import source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_IMPORT,
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_form(hass):
    """Test we get the form with user source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_IMPORT,
    )

    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
