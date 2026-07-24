"""Tests for Swiss Hydrological Data config flow."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError

from homeassistant.components.swiss_hydrological_data.const import CONF_STATION, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import STATION_DATA, STATION_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_user(hass: HomeAssistant, mock_swiss_hydro_data: MagicMock) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: STATION_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aare Bern"
    assert result["result"].unique_id == str(STATION_ID)
    assert result["data"] == {CONF_STATION: STATION_ID}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_swiss_hydro_data: MagicMock,
) -> None:
    """Test error when station is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: STATION_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "return_value", "error_key"),
    [
        pytest.param(
            ConnectionError("Connection failed"),
            None,
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(RuntimeError("Unexpected"), None, "unknown", id="unknown_error"),
        pytest.param(None, None, "invalid_station", id="station_not_found"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors_can_recover(
    hass: HomeAssistant,
    mock_swiss_hydro_data: MagicMock,
    side_effect: Exception | None,
    return_value: None,
    error_key: str,
) -> None:
    """Test errors and recovery during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_swiss_hydro_data.get_station.side_effect = side_effect
    mock_swiss_hydro_data.get_station.return_value = return_value

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: STATION_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_swiss_hydro_data.get_station.side_effect = None
    mock_swiss_hydro_data.get_station.return_value = STATION_DATA

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: STATION_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aare Bern"
    assert result["result"].unique_id == str(STATION_ID)
