"""Tests for the MeteoAlarm config flow."""

from unittest.mock import AsyncMock, MagicMock

from meteoalarmapi import ServerError, UnexpectedError, WrongCountry
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.meteoalarm.const import CONF_PROVINCE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {CONF_COUNTRY: "ES", CONF_PROVINCE: "Mallorca", CONF_LANGUAGE: "en"}
ENTRY_DATA = {CONF_COUNTRY: "spain", CONF_PROVINCE: "Mallorca", CONF_LANGUAGE: "en"}


@pytest.mark.usefixtures("mock_meteoalert")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test a region is added from the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mallorca"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == "spain_mallorca_en"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_meteoalert")
async def test_user_flow_default_language(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the language defaults to Home Assistant's language."""
    hass.config.language = "de"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "DE", CONF_PROVINCE: "Kreis Wunsiedel"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_COUNTRY: "germany",
        CONF_PROVINCE: "Kreis Wunsiedel",
        CONF_LANGUAGE: "de",
    }
    assert result["result"].unique_id == "germany_kreis wunsiedel_de"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WrongCountry("no feed"), "invalid_country"),
        (ServerError("500"), "cannot_connect"),
        (UnexpectedError("timeout"), "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_meteoalert: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the form shows an error when the feed can't be fetched, then recovers."""
    mock_meteoalert.return_value.get_alert.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_meteoalert.return_value.get_alert.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_meteoalert", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a region can only be added once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY: "NL", CONF_PROVINCE: "TEST PROVINCE", CONF_LANGUAGE: "en-GB"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_meteoalert")
async def test_import_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test a YAML configuration is imported, titled with its YAML name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**ENTRY_DATA, CONF_COUNTRY: "Spain", CONF_NAME: "meteoalarm"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "meteoalarm"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == "spain_mallorca_en"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (WrongCountry("no feed"), "invalid_country"),
        (ServerError("500"), "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_meteoalert: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test the import aborts when the feed can't be fetched."""
    mock_meteoalert.return_value.get_alert.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**ENTRY_DATA, CONF_NAME: "meteoalarm"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
