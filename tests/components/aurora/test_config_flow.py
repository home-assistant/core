"""Test the Aurora config flow."""

from unittest.mock import patch

from aiohttp import ClientError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.aurora.const import DOMAIN

from tests.common import MockConfigEntry

DATA = {
    "name": "Home",
    "latitude": -10,
    "longitude": 10.2,
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aurora.config_flow.AuroraForecast.get_forecast_data",
        return_value=True,
    ), patch(
        "homeassistant.components.aurora.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Aurora - Home"
    assert result2["data"] == DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test if invalid response or no connection returned from the API."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aurora.AuroraForecast.get_forecast_data",
        side_effect=ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_with_unknown_error(hass):
    """Test with unknown error response from the API."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aurora.AuroraForecast.get_forecast_data",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_option_flow(hass):
    """Test option flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)

    assert not entry.options

    with patch("homeassistant.components.aurora.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(
            entry.entry_id,
            data=None,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"forecast_threshold": 65},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"]["forecast_threshold"] == 65
