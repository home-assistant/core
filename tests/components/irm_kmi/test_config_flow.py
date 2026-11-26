"""Tests for the IRM KMI config flow."""

from unittest.mock import AsyncMock

from irm_kmi_api import IrmKmiApiError, RadarStyle
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.irm_kmi.const import (
    CONF_DARK_MODE,
    CONF_LANGUAGE_OVERRIDE,
    CONF_LANGUAGE_OVERRIDE_OPTIONS,
    CONF_RADAR_STYLE,
    CONF_RADAR_STYLE_OPTIONS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_flow_forecast")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brussels"
    assert result["data"] == {
        CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456},
        CONF_UNIQUE_ID: "brussels be",
    }
    assert result["result"].unique_id == "brussels be"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_location_out_benelux(
    hass: HomeAssistant, mock_config_flow_forecast: AsyncMock
) -> None:
    """Test configuration flow with a location outside of Benelux."""
    mock_config_flow_forecast.side_effect = [
        await async_load_json_object_fixture(
            hass, "forecast_out_of_benelux.json", DOMAIN
        ),
        mock_config_flow_forecast.return_value,
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 0.123, CONF_LONGITUDE: 0.456}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_LOCATION: "out_of_benelux"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brussels"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_with_api_error(
    hass: HomeAssistant, mock_config_flow_forecast: AsyncMock
) -> None:
    """Test when API returns an error during the configuration flow."""
    mock_config_flow_forecast.side_effect = IrmKmiApiError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_error"


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_flow_forecast")
async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the location is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 50.123, CONF_LONGITUDE: 4.456}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_option_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test when the user changes options with the option flow."""
    mock_config_entry.add_to_hass(hass)

    assert not mock_config_entry.options

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DARK_MODE: False,
        CONF_LANGUAGE_OVERRIDE: "none",
        CONF_RADAR_STYLE: RadarStyle.OPTION_STYLE_STD,
    }

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DARK_MODE: True,
            CONF_LANGUAGE_OVERRIDE: "fr",
            CONF_RADAR_STYLE: RadarStyle.OPTION_STYLE_YELLOW_RED,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DARK_MODE: True,
        CONF_LANGUAGE_OVERRIDE: "fr",
        CONF_RADAR_STYLE: RadarStyle.OPTION_STYLE_YELLOW_RED,
    }

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["data_schema"] is not None
    assert {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    } == {
        CONF_DARK_MODE: True,
        CONF_LANGUAGE_OVERRIDE: "fr",
        CONF_RADAR_STYLE: RadarStyle.OPTION_STYLE_YELLOW_RED,
    }


@pytest.mark.parametrize(
    ("selector", "options"),
    [
        pytest.param(
            CONF_LANGUAGE_OVERRIDE,
            CONF_LANGUAGE_OVERRIDE_OPTIONS,
            id="language_override",
        ),
        pytest.param(CONF_RADAR_STYLE, CONF_RADAR_STYLE_OPTIONS, id="radar_style"),
    ],
)
async def test_selector_options_are_translated(
    hass: HomeAssistant, selector: str, options: list[str]
) -> None:
    """Test every option of a selector has a translation."""
    translations = await async_get_translations(hass, "en", "selector", {DOMAIN})
    prefix = f"component.{DOMAIN}.selector.{selector}.options."

    assert {
        key.removeprefix(prefix) for key in translations if key.startswith(prefix)
    } == set(options)
