"""Test the Smhi config flow."""

from __future__ import annotations

from unittest.mock import patch

from smhi.smhi_lib import SmhiForecastException

from homeassistant import config_entries
from homeassistant.components.smhi.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and create an entry."""

    hass.config.latitude = 0.0
    hass.config.longitude = 0.0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
            return_value={"test": "something", "test2": "something else"},
        ),
        patch(
            "homeassistant.components.smhi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
    with (
        patch(
            "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
            return_value={"test": "something", "test2": "something else"},
        ),
        patch(
            "homeassistant.components.smhi.async_setup_entry",
            return_value=True,
        ),
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

    assert result4["type"] is FlowResultType.CREATE_ENTRY
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

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_location"}

    # Continue flow with new coordinates
    with (
        patch(
            "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
            return_value={"test": "something", "test2": "something else"},
        ),
        patch(
            "homeassistant.components.smhi.async_setup_entry",
            return_value=True,
        ),
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

    assert result3["type"] is FlowResultType.CREATE_ENTRY
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

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test re-configuration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="57.2898-13.6304",
        data={"location": {"latitude": 57.2898, "longitude": 13.6304}, "name": "Home"},
        version=2,
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        WEATHER_DOMAIN, DOMAIN, "57.2898, 13.6304"
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "57.2898, 13.6304")},
        manufacturer="SMHI",
        model="v2",
        name=entry.title,
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
        side_effect=SmhiForecastException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: 0.0,
                    CONF_LONGITUDE: 0.0,
                }
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_location"}

    with (
        patch(
            "homeassistant.components.smhi.config_flow.Smhi.async_get_forecast",
            return_value={"test": "something", "test2": "something else"},
        ),
        patch(
            "homeassistant.components.smhi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: 58.2898,
                    CONF_LONGITUDE: 14.6304,
                }
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.title == "Home"
    assert entry.unique_id == "58.2898-14.6304"
    assert entry.data == {
        "location": {
            "latitude": 58.2898,
            "longitude": 14.6304,
        },
        "name": "Home",
    }
    entity = entity_registry.async_get(entity.entity_id)
    assert entity
    assert entity.unique_id == "58.2898, 14.6304"
    device = device_registry.async_get(device.id)
    assert device
    assert device.identifiers == {(DOMAIN, "58.2898, 14.6304")}
    assert len(mock_setup_entry.mock_calls) == 1
