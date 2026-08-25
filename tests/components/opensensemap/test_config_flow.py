"""Tests for the openSenseMap config flow."""

from unittest.mock import AsyncMock

from opensensemap_api.exceptions import OpenSenseMapError
import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_STATION_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_opensensemap_api: AsyncMock) -> None:
    """Test the user-initiated config flow happy path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Station"
    assert result["data"] == {CONF_STATION_ID: TEST_STATION_ID}
    assert result["result"].unique_id == TEST_STATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
) -> None:
    """Test that API errors during the user flow surface as form errors."""
    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recovery after the error is cleared.
    mock_opensensemap_api.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Station"
    assert result["data"] == {CONF_STATION_ID: TEST_STATION_ID}
    assert result["result"].unique_id == TEST_STATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_invalid_station(
    hass: HomeAssistant, mock_opensensemap_api: AsyncMock, station_data: dict
) -> None:
    """Test that a station with no name is rejected."""
    mock_opensensemap_api.data = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_station"}

    mock_opensensemap_api.data = station_data
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that adding a duplicate station is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow(
    hass: HomeAssistant, mock_opensensemap_api: AsyncMock
) -> None:
    """Test importing a YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Station"
    assert result["data"] == {CONF_STATION_ID: TEST_STATION_ID}
    assert result["result"].unique_id == TEST_STATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_with_yaml_name(
    hass: HomeAssistant, mock_opensensemap_api: AsyncMock
) -> None:
    """Test that an explicit YAML name is used as the title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID, CONF_NAME: "My Station"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Station"
    assert result["data"] == {CONF_STATION_ID: TEST_STATION_ID}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_with_yaml_name_cannot_connect(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
) -> None:
    """Test importing with a YAML name still validates the station."""
    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID, CONF_NAME: "My Station"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_cannot_connect(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
) -> None:
    """Test importing when the API is unreachable."""
    mock_opensensemap_api.get_data.side_effect = OpenSenseMapError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_invalid_station(
    hass: HomeAssistant, mock_opensensemap_api: AsyncMock
) -> None:
    """Test importing a station that does not exist."""
    mock_opensensemap_api.data = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_station"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing a YAML configuration that already has a config entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
