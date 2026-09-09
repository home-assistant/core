"""Test the Foreca config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyforeca import ForecaAuthError, ForecaConnectionError
import pytest

from homeassistant.components.foreca.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {CONF_API_KEY: "test-key"}
LOCATION_INPUT = {CONF_LOCATION: {CONF_LATITUDE: 60.17, CONF_LONGITUDE: 24.94}}


@pytest.mark.usefixtures("mock_setup_entry", "mock_foreca_client")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the API key is all the entry needs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Foreca"
    assert result["data"] == {CONF_API_KEY: "test-key"}
    # A new entry starts with the Home Assistant home location, so setting the
    # integration up produces a weather entity without a second step.
    assert [subentry["data"] for subentry in result["subentries"]] == [
        {CONF_LATITUDE: hass.config.latitude, CONF_LONGITUDE: hass.config.longitude}
    ]


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ForecaAuthError, "invalid_auth"),
        (ForecaConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors_then_recovers(
    hass: HomeAssistant,
    mock_foreca_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a bad key keeps the form open, then succeeds once it is fixed."""
    mock_foreca_client.location_info.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_foreca_client.location_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_foreca_client")
async def test_add_second_location(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a second location is added to the same entry as a subentry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 48.86, CONF_LONGITUDE: 2.35}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helsinki"
    assert result["data"] == {CONF_LATITUDE: 48.86, CONF_LONGITUDE: 2.35}


@pytest.mark.usefixtures("mock_foreca_client")
async def test_duplicate_location_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a location that is already configured aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], LOCATION_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [(ForecaConnectionError, "cannot_connect"), (RuntimeError, "unknown")],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_subentry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a location the API cannot serve keeps the form open."""
    mock_config_entry.add_to_hass(hass)
    mock_foreca_client.location_info.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 48.86, CONF_LONGITUDE: 2.35}},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_entry_title_falls_back_without_location_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test the subentry title falls back when the API returns no name."""
    mock_config_entry.add_to_hass(hass)
    mock_foreca_client.location_info = AsyncMock(
        return_value=type("L", (), {"name": None})()
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 48.86, CONF_LONGITUDE: 2.35}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Foreca"


@pytest.mark.usefixtures("mock_setup_entry", "mock_foreca_client")
async def test_duplicate_api_key_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same API key cannot be set up twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
