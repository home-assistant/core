"""Test the World Air Quality Index (WAQI) config flow."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIAuthenticationError, WAQIConnectionError, WAQIError
import pytest

from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LOCATION,
    ATTR_LONGITUDE,
    CONF_API_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def second_mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="WAQI",
        data={CONF_API_KEY: "asdf"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data={CONF_STATION_NUMBER: 4584},
                subentry_id="ABCDEF",
                subentry_type="station",
                title="de Jongweg, Utrecht",
                unique_id="4584",
            )
        ],
    )


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_waqi: AsyncMock
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asd"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "World Air Quality Index"
    assert result["data"] == {CONF_API_KEY: "asd"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIAuthenticationError("Test error"), "invalid_auth"),
        (WAQIConnectionError("Test error"), "cannot_connect"),
        (Exception("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_entry_errors(
    hass: HomeAssistant, mock_waqi: AsyncMock, exception: Exception, error: str
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_waqi.get_by_ip.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asd"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["step_id"] == "user"

    mock_waqi.get_by_ip.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asd"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant, mock_waqi: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate entry handling."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asd"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_map_flow(
    hass: HomeAssistant, mock_waqi: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we get the form."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "map"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 10.0},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {CONF_STATION_NUMBER: 4584}
    assert list(mock_config_entry.subentries.values())[1].unique_id == "4584"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIConnectionError("Test error"), "cannot_connect"),
        (Exception("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_map_flow_errors(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "map"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert not result["errors"]

    mock_waqi.get_by_coordinates.side_effect = exception

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 10.0},
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_coordinates.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 10.0},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_map_duplicate(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    second_mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate location handling."""
    mock_config_entry.add_to_hass(hass)
    second_mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "map"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 10.0},
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_station_number_flow(
    hass: HomeAssistant, mock_waqi: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the station number flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "station_number"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_number"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {CONF_STATION_NUMBER: 4584}
    assert list(mock_config_entry.subentries.values())[1].unique_id == "4584"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIConnectionError("Test error"), "cannot_connect"),
        (Exception("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_station_number_flow_errors(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "station_number"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_number"
    assert not result["errors"]

    mock_waqi.get_by_station_number.side_effect = exception

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_number"
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_station_number.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_station_number_duplicate(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    second_mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate station number handling."""
    mock_config_entry.add_to_hass(hass)
    second_mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "station_number"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_number"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_reconfigure_flow(
    hass: HomeAssistant, mock_waqi: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the station number."""
    mock_config_entry.add_to_hass(hass)
    subentry_id = list(mock_config_entry.subentries)[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry.subentries[subentry_id]
    assert subentry.data == {CONF_STATION_NUMBER: 4584}
    assert subentry.title == "de Jongweg, Utrecht"
    assert subentry.unique_id == "4584"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIConnectionError("Test error"), "cannot_connect"),
        (Exception("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form on reconfigure errors."""
    mock_config_entry.add_to_hass(hass)
    subentry_id = list(mock_config_entry.subentries)[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_waqi.get_by_station_number.side_effect = exception

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_station_number.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_duplicate(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    second_mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring to a station number already used by another subentry."""
    mock_config_entry.add_to_hass(hass)
    second_mock_config_entry.add_to_hass(hass)
    subentry_id = list(mock_config_entry.subentries)[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_recovers_from_setup_retry(
    hass: HomeAssistant, mock_waqi: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an unreachable station recovers the entry from setup retry."""
    mock_waqi.get_by_station_number.side_effect = WAQIError("Could not find station")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_waqi.get_by_station_number.side_effect = None
    subentry_id = list(mock_config_entry.subentries)[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_NUMBER: 4584},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    subentry = mock_config_entry.subentries[subentry_id]
    assert subentry.data == {CONF_STATION_NUMBER: 4584}
    assert subentry.unique_id == "4584"
