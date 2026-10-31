"""Test the London Air config flow."""

from unittest.mock import AsyncMock

from pylondonair import LondonAirConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.london_air.const import CONF_LOCATIONS, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_success(
    hass: HomeAssistant, mock_london_air_client: AsyncMock
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATIONS: ["Merton", "Barnet"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Air"
    assert result["data"] == {CONF_LOCATIONS: ["Merton", "Barnet"]}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_london_air_client: AsyncMock
) -> None:
    """Test the user flow when the API cannot be reached."""
    mock_london_air_client.async_test_connection.side_effect = LondonAirConnectionError(
        "Request to London Air API failed"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    mock_london_air_client.async_test_connection.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_required(
    hass: HomeAssistant, mock_london_air_client: AsyncMock
) -> None:
    """Test the user flow when no locations are selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATIONS: []},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_LOCATIONS] == "required"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_london_air_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when an entry already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_success(
    hass: HomeAssistant, mock_london_air_client: AsyncMock
) -> None:
    """Test a successful YAML import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Air"
    assert result["data"] == {CONF_LOCATIONS: ["Merton"]}


async def test_import_cannot_connect(
    hass: HomeAssistant, mock_london_air_client: AsyncMock
) -> None:
    """Test a YAML import that fails to connect."""
    mock_london_air_client.async_test_connection.side_effect = LondonAirConnectionError(
        "Request to London Air API failed"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_already_configured(
    hass: HomeAssistant,
    mock_london_air_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a YAML import aborts when an entry already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
