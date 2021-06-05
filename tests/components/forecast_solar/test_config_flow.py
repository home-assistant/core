"""Test the Forecast Solar config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.forecast_solar.const import DOMAIN, TEST_DATA

from tests.common import MockConfigEntry


async def test_config_flow_setup(hass):
    """Test config flow setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.forecast_solar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result["type"] == "create_entry"


async def test_options_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=TEST_DATA
    )

    with patch(
        "homeassistant.components.forecast_solar.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.forecast_solar.async_unload_entry", return_value=True
    ):
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert entry.options == TEST_DATA
