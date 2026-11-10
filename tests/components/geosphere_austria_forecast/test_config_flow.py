"""Test the GeoSphere Austria Forecast config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zamg import ZamgApiError, ZamgNoDataError

from homeassistant.components.geosphere_austria_forecast.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

LOCATION_INPUT = {CONF_LOCATION: {CONF_LATITUDE: 48.2877, CONF_LONGITUDE: 15.98486}}

FLOW_ERRORS = [
    pytest.param(ZamgApiError("Bad request", status_code=400), "outside_coverage"),
    pytest.param(ZamgApiError("Server error", status_code=500), "cannot_connect"),
    pytest.param(
        ZamgApiError("Too many requests", status_code=429, rate_limit_reset=60),
        "cannot_connect",
    ),
    pytest.param(ZamgNoDataError("Invalid data"), "cannot_connect"),
    pytest.param(RuntimeError("Unexpected"), "unknown"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_nwp_client: MagicMock) -> None:
    """Test adding a location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "48.29, 15.98"
    assert result["data"] == {CONF_LATITUDE: 48.2877, CONF_LONGITUDE: 15.98486}
    assert result["result"].unique_id == "48.2850-15.9802"
    assert mock_nwp_client.request_timeout == 60


@pytest.mark.usefixtures("mock_setup_entry", "mock_nwp_client")
async def test_home_location_is_named_after_home(hass: HomeAssistant) -> None:
    """Test the location keeps the home name when the pin is not moved."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
            }
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == hass.config.location_name
    assert result["result"].unique_id == "48.2850-15.9802"


@pytest.mark.parametrize(("exception", "error"), FLOW_ERRORS)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors_then_recovers(
    hass: HomeAssistant,
    mock_nwp_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a failed check keeps the form open, then succeeds."""
    mock_nwp_client.get_forecast.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_nwp_client.get_forecast.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_nwp_client")
async def test_same_grid_point_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a location on the grid point of a configured one aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 48.2869, CONF_LONGITUDE: 15.9811}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
