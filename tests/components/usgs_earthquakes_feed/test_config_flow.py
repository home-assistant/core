"""Define tests for the USGS Earthquakes Feed config flow."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.usgs_earthquakes_feed import (
    CONF_FEED_TYPE,
    CONF_MINIMUM_MAGNITUDE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    hass.config.latitude = -31.0
    hass.config.longitude = 150.0
    conf = {
        CONF_LATITUDE: -31.0,
        CONF_LONGITUDE: 150.0,
        CONF_FEED_TYPE: "past_hour_m25_earthquakes",
        CONF_RADIUS: 200,
        CONF_MINIMUM_MAGNITUDE: 0.0,
    }

    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup",
            return_value=True,
        ),
    ):
        # Create first entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Try to create duplicate
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_import(hass: HomeAssistant) -> None:
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: -31.0,
        CONF_LONGITUDE: 150.0,
        CONF_FEED_TYPE: "past_hour_m25_earthquakes",
        CONF_RADIUS: 200,
        CONF_MINIMUM_MAGNITUDE: 0.0,
        CONF_SCAN_INTERVAL: timedelta(minutes=5),
    }

    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "past_hour_m25_earthquakes"
    assert result["data"] == {
        CONF_LATITUDE: -31.0,
        CONF_LONGITUDE: 150.0,
        CONF_FEED_TYPE: "past_hour_m25_earthquakes",
        CONF_RADIUS: 200,
        CONF_MINIMUM_MAGNITUDE: 0.0,
        CONF_SCAN_INTERVAL: 300.0,
    }


async def test_step_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    hass.config.latitude = -31.0
    hass.config.longitude = 150.0
    conf = {
        CONF_LATITUDE: -31.0,
        CONF_LONGITUDE: 150.0,
        CONF_FEED_TYPE: "past_day_m45_earthquakes",
        CONF_RADIUS: 100,
        CONF_MINIMUM_MAGNITUDE: 2.5,
    }

    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "past_day_m45_earthquakes"
    assert result["data"] == {
        CONF_LATITUDE: -31.0,
        CONF_LONGITUDE: 150.0,
        CONF_FEED_TYPE: "past_day_m45_earthquakes",
        CONF_RADIUS: 100,
        CONF_MINIMUM_MAGNITUDE: 2.5,
        CONF_SCAN_INTERVAL: 300.0,
    }


async def test_step_user_with_multiple_instances(hass: HomeAssistant) -> None:
    """Test that multiple instances can be configured."""
    hass.config.latitude = -31.0
    hass.config.longitude = 150.0

    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup",
            return_value=True,
        ),
    ):
        # Create first instance
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_LATITUDE: -31.0,
                CONF_LONGITUDE: 150.0,
                CONF_FEED_TYPE: "past_hour_m25_earthquakes",
                CONF_RADIUS: 200,
                CONF_MINIMUM_MAGNITUDE: 0.0,
            },
        )
        assert result1["type"] is FlowResultType.CREATE_ENTRY
        assert result1["title"] == "past_hour_m25_earthquakes"

        # Create second instance with different feed type
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_LATITUDE: -31.0,
                CONF_LONGITUDE: 150.0,
                CONF_FEED_TYPE: "past_day_m45_earthquakes",
                CONF_RADIUS: 100,
                CONF_MINIMUM_MAGNITUDE: 2.5,
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "past_day_m45_earthquakes"


async def test_step_reconfigure(hass: HomeAssistant, config_entry) -> None:
    """Test that reconfiguration works."""
    config_entry.add_to_hass(hass)

    # Start reconfiguration
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Update configuration
    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LATITUDE: -31.0,
                CONF_LONGITUDE: 150.0,
                CONF_FEED_TYPE: "past_day_m25_earthquakes",
                CONF_RADIUS: 150,
                CONF_MINIMUM_MAGNITUDE: 1.5,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_FEED_TYPE] == "past_day_m25_earthquakes"
    assert config_entry.data[CONF_RADIUS] == 150
    assert config_entry.data[CONF_MINIMUM_MAGNITUDE] == 1.5


async def test_options_flow(hass: HomeAssistant, config_entry) -> None:
    """Test options flow."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.usgs_earthquakes_feed.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Start options flow
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Update options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_LATITUDE: -31.0,
                CONF_LONGITUDE: 150.0,
                CONF_FEED_TYPE: "past_week_m45_earthquakes",
                CONF_RADIUS: 250,
                CONF_MINIMUM_MAGNITUDE: 3.0,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.data[CONF_FEED_TYPE] == "past_week_m45_earthquakes"
        assert config_entry.data[CONF_RADIUS] == 250
        assert config_entry.data[CONF_MINIMUM_MAGNITUDE] == 3.0

