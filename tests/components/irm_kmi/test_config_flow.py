"""Tests for the IRM KMI config flow."""

from unittest.mock import MagicMock

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LOCATION,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_in_benelux: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.123, ATTR_LONGITUDE: 4.456}},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Brussels"
    assert result.get("data") == {
        CONF_LOCATION: {ATTR_LATITUDE: 50.123, ATTR_LONGITUDE: 4.456},
        CONF_UNIQUE_ID: "brussels be",
    }


async def test_user_flow_home(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_in_benelux: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.123, ATTR_LONGITUDE: 4.456}},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Brussels"


async def test_config_flow_location_out_benelux(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_out_benelux_then_in_belgium: MagicMock,
) -> None:
    """Test configuration flow with a zone outside of Benelux."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 0.123, ATTR_LONGITUDE: 0.456}},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert CONF_LOCATION in result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.123, ATTR_LONGITUDE: 4.456}},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_config_flow_with_api_error(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_api_error: MagicMock,
) -> None:
    """Test when API returns an error during the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.123, ATTR_LONGITUDE: 4.456}},
    )

    assert result.get("type") is FlowResultType.ABORT


async def test_setup_twice_same_location(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_in_benelux: MagicMock,
) -> None:
    """Test when the user tries to set up the weather twice for the same location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.5, ATTR_LONGITUDE: 4.6}},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY

    # Set up a second time
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {ATTR_LATITUDE: 50.5, ATTR_LONGITUDE: 4.6}},
    )
    assert result.get("type") is FlowResultType.ABORT


async def test_option_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test when the user changes options with the option flow."""
    mock_config_entry.add_to_hass(hass)

    assert not mock_config_entry.options

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id, data=None
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_LANGUAGE_OVERRIDE: "none"}
