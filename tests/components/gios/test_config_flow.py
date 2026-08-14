"""Define tests for the GIOS config flow."""

from unittest.mock import MagicMock

from gios import ApiError, InvalidSensorsDataError
import pytest

from homeassistant.components.gios.const import CONF_STATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {
    CONF_STATION_ID: "123",
}

pytestmark = pytest.mark.usefixtures("mock_gios")


async def test_happy_flow(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert len(result["data_schema"].schema[CONF_STATION_ID].config["options"]) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {
        CONF_STATION_ID: 123,
        CONF_NAME: "Home",
    }

    assert result["result"].unique_id == "123"


async def test_form_with_api_error(hass: HomeAssistant, mock_gios: MagicMock) -> None:
    """Test the form is aborted because of API error."""
    mock_gios.create.side_effect = ApiError("error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("exception", "errors"),
    [
        (
            InvalidSensorsDataError("Invalid data"),
            {CONF_STATION_ID: "invalid_sensors_data"},
        ),
        (ApiError("error"), {"base": "cannot_connect"}),
    ],
)
async def test_form_submission_errors(
    hass: HomeAssistant, mock_gios: MagicMock, exception, errors
) -> None:
    """Test errors during form submission."""
    mock_gios.async_update.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    mock_gios.async_update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"


async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that duplicate station IDs are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
