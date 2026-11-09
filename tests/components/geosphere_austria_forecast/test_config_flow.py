"""Test the GeoSphere Austria Forecast config flow."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zamg import ZamgApiError, ZamgNoDataError

from homeassistant.components.geosphere_austria_forecast.const import (
    DOMAIN,
    SUBENTRY_TYPE_LOCATION,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

LOCATION_INPUT = {CONF_LOCATION: {CONF_LATITUDE: 48.2877, CONF_LONGITUDE: 15.98486}}
SECOND_LOCATION_INPUT = {
    CONF_NAME: "Graz",
    CONF_LOCATION: {CONF_LATITUDE: 47.07, CONF_LONGITUDE: 15.44},
}

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
    """Test setting up the integration with a first location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GeoSphere Austria Forecast"
    assert result["data"] == {}
    subentries = list(result["result"].subentries.values())
    assert len(subentries) == 1
    assert subentries[0].subentry_type == SUBENTRY_TYPE_LOCATION
    assert subentries[0].title == "48.29, 15.98"
    assert subentries[0].data == {CONF_LATITUDE: 48.2877, CONF_LONGITUDE: 15.98486}
    assert subentries[0].unique_id == "48.2850-15.9802"
    assert mock_nwp_client.request_timeout == 60


@pytest.mark.usefixtures("mock_setup_entry", "mock_nwp_client")
async def test_home_location_is_named_after_home(hass: HomeAssistant) -> None:
    """Test the first location keeps the home name when the pin is not moved."""
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
    subentry = next(iter(result["result"].subentries.values()))
    assert subentry.title == hass.config.location_name


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
async def test_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only one entry can be set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_add_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test a location is added as a subentry with its name."""
    mock_config_entry.add_to_hass(hass)
    mock_nwp_client.get_forecast.return_value = replace(
        mock_nwp_client.get_forecast.return_value,
        resolved_latitude=47.07,
        resolved_longitude=15.44,
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SECOND_LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Graz"
    assert result["data"] == {CONF_LATITUDE: 47.07, CONF_LONGITUDE: 15.44}
    assert result["unique_id"] == "47.0700-15.4400"


@pytest.mark.usefixtures("mock_nwp_client")
async def test_same_grid_point_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a location on the grid point of a configured one aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Pixendorf village",
            CONF_LOCATION: {CONF_LATITUDE: 48.2869, CONF_LONGITUDE: 15.9811},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("exception", "error"), FLOW_ERRORS)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_errors_then_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a failed check keeps the location form open, then succeeds."""
    mock_config_entry.add_to_hass(hass)
    mock_nwp_client.get_forecast.return_value = replace(
        mock_nwp_client.get_forecast.return_value,
        resolved_latitude=47.07,
        resolved_longitude=15.44,
    )
    mock_nwp_client.get_forecast.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LOCATION),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SECOND_LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_nwp_client.get_forecast.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SECOND_LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
