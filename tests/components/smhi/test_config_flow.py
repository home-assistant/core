"""Test the Smhi config flow."""
from __future__ import annotations

from unittest.mock import patch

from smhi.smhi_lib import SmhiForecastException

from homeassistant import config_entries
from homeassistant.components.smhi.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and create an entry."""

    hass.config.latitude = 0.0
    hass.config.longitude = 0.0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
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
                CONF_LOCATION: {
                    CONF_LATITUDE: 0.0,
                    CONF_LONGITUDE: 0.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Home"
    assert result2["data"] == {
        "location": {
            "latitude": 0.0,
            "longitude": 0.0,
        },
        "name": "Home",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Check title is "Weather" when not home coordinates
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
                CONF_LOCATION: {
                    CONF_LATITUDE: 1.0,
                    CONF_LONGITUDE: 1.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Weather 1.0 1.0"
    assert result4["data"] == {
        "location": {
            "latitude": 1.0,
            "longitude": 1.0,
        },
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
                CONF_LOCATION: {
                    CONF_LATITUDE: 0.0,
                    CONF_LONGITUDE: 0.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_location"}

    # Continue flow with new coordinates
    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        return_value={"test": "something", "test2": "something else"},
    ), patch(
        "homeassistant.components.smhi.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: 2.0,
                    CONF_LONGITUDE: 2.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Weather 2.0 2.0"
    assert result3["data"] == {
        "location": {
            "latitude": 2.0,
            "longitude": 2.0,
        },
        "name": "Weather",
    }


async def test_form_unique_id_exist(hass: HomeAssistant) -> None:
    """Test we handle unique id already exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.0-1.0",
        data={
            "location": {
                "latitude": 1.0,
                "longitude": 1.0,
            },
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: 1.0,
                    CONF_LONGITUDE: 1.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
