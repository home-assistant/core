"""Tests for the RDW config flow."""

from unittest.mock import MagicMock

from vehicle.exceptions import RDWConnectionError, RDWUnknownLicensePlateError

from homeassistant.components.rdw.const import CONF_LICENSE_PLATE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant, mock_rdw_config_flow: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "11-ZKZ-3",
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "11-ZKZ-3"
    assert result2.get("data") == {CONF_LICENSE_PLATE: "11ZKZ3"}


async def test_full_flow_with_authentication_error(
    hass: HomeAssistant, mock_rdw_config_flow: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test the full user configuration flow with incorrect license plate.

    This tests tests a full config flow, with a case the user enters an invalid
    license plate, but recover by entering the correct one.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    mock_rdw_config_flow.vehicle.side_effect = RDWUnknownLicensePlateError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "0001TJ",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"base": "unknown_license_plate"}

    mock_rdw_config_flow.vehicle.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_LICENSE_PLATE: "11-ZKZ-3",
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "11-ZKZ-3"
    assert result3.get("data") == {CONF_LICENSE_PLATE: "11ZKZ3"}


async def test_connection_error(
    hass: HomeAssistant, mock_rdw_config_flow: MagicMock
) -> None:
    """Test API connection error."""
    mock_rdw_config_flow.vehicle.side_effect = RDWConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_LICENSE_PLATE: "0001TJ"},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
