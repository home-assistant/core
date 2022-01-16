"""Test the Smhi config flow."""
from __future__ import annotations

from unittest.mock import patch

from smhi.smhi_lib import SmhiForecastException

from homeassistant import config_entries
from homeassistant.components.smhi.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    hass.config.latitude = 0.0
    hass.config.longitude = 0.0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        return_value={"test": "something", "test2": "something else"},
    ), patch(
        "homeassistant.components.smhi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: 0.0,
                CONF_LONGITUDE: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Home"
    assert result2["data"] == {
        "latitude": 0.0,
        "longitude": 0.0,
        "name": "Home",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        return_value={"test": "something", "test2": "something else"},
    ), patch(
        "homeassistant.components.smhi.async_setup_entry",
        return_value=True,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_LATITUDE: 1.0,
                CONF_LONGITUDE: 1.0,
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result4["title"] == "Weather"
    assert result4["data"] == {
        "latitude": 1.0,
        "longitude": 1.0,
        "name": "Weather",
    }


async def test_form_invalid_coordinates(hass: HomeAssistant) -> None:
    """Test we handle invalid coordinates."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        side_effect=SmhiForecastException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: 0.0,
                CONF_LONGITUDE: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "wrong_location"}


async def test_form_unique_id_exist(hass: HomeAssistant) -> None:
    """Test we handle invalid coordinates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.0-1.0",
        data={
            "latitude": 1.0,
            "longitude": 1.0,
            "name": "Weather",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        return_value={"test": "something", "test2": "something else"},
    ), patch(
        "homeassistant.components.yale_smart_alarm.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: 1.0,
                CONF_LONGITUDE: 1.0,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
