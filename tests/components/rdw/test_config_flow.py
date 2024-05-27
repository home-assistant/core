"""Tests for the RDW config flow."""

from unittest.mock import AsyncMock, MagicMock

from vehicle.exceptions import RDWConnectionError, RDWUnknownLicensePlateError

from homeassistant.components.rdw.const import CONF_LICENSE_PLATE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant, mock_rdw: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "11-ZKZ-3",
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "11-ZKZ-3"
    assert result.get("data") == {CONF_LICENSE_PLATE: "11ZKZ3"}


async def test_full_flow_with_authentication_error(
    hass: HomeAssistant, mock_rdw: AsyncMock, mock_setup_entry: MagicMock
) -> None:
    """Test the full user configuration flow with incorrect license plate.

    This test tests a full config flow, with a case the user enters an invalid
    license plate, but recover by entering the correct one.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_rdw.vehicle.side_effect = RDWUnknownLicensePlateError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "0001TJ",
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "unknown_license_plate"}

    mock_rdw.vehicle.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "11-ZKZ-3",
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "11-ZKZ-3"
    assert result.get("data") == {CONF_LICENSE_PLATE: "11ZKZ3"}


async def test_connection_error(hass: HomeAssistant, mock_rdw: AsyncMock) -> None:
    """Test API connection error."""
    mock_rdw.vehicle.side_effect = RDWConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_LICENSE_PLATE: "0001TJ"},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
