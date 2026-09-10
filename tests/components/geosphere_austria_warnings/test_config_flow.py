"""Tests for the GeoSphere Austria Warnings config flow."""

from unittest.mock import AsyncMock

from pygeosphere_warnings import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
)
import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_LATITUDE, TEST_LONGITUDE

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_client")

USER_INPUT = {
    CONF_LOCATION: {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}
}


async def test_full_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schwechat"
    assert result["data"] == {
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }
    assert result["result"].unique_id == "30740"
    mock_client.get_warnings_for_coords.assert_called_once_with(
        TEST_LATITUDE, TEST_LONGITUDE
    )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            GeoSphereMunicipalityNotFoundError,
            "municipality_not_found",
            id="municipality_not_found",
        ),
        pytest.param(GeoSphereConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(GeoSphereApiError, "cannot_connect", id="api_error"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test that errors are shown and the flow can recover."""
    mock_client.get_warnings_for_coords.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.get_warnings_for_coords.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a municipality can only be configured once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
