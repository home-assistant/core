"""Test the World Air Quality Index (WAQI) config flow."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIAuthenticationError, WAQIConnectionError
import pytest

from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.config_entries import (
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


@pytest.mark.parametrize(
    "api_key",
    [
        pytest.param("new_key", id="new_key"),
        pytest.param("asd", id="same_key"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    api_key: str,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    mock_waqi.authenticate.assert_called_with(api_key)


@pytest.mark.parametrize(
    "api_key",
    [
        pytest.param("new_key", id="new_key"),
        pytest.param("asd", id="same_key"),
    ],
)
async def test_reauth_flow_loaded_entry(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    api_key: str,
) -> None:
    """Test reauthenticating a loaded entry reloads it once."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await mock_config_entry.start_reauth_flow(hass)
    mock_waqi.get_by_station_number.reset_mock()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Each setup fetches the single station once, so one call means one reload
    mock_waqi.get_by_station_number.assert_awaited_once()


async def test_reauth_flow_setup_failed_entry(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthenticating an entry that failed setup reloads it with the new key."""
    mock_waqi.get_by_station_number.side_effect = WAQIAuthenticationError
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_waqi.get_by_station_number.side_effect = None
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data == {CONF_API_KEY: "new_key"}
    mock_waqi.authenticate.assert_called_with("new_key")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIAuthenticationError("Test error"), "invalid_auth"),
        (WAQIConnectionError("Test error"), "cannot_connect"),
        (Exception("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_waqi.get_by_ip.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_ip.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: "new_key"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_duplicate(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    second_mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication with the API key of another entry aborts."""
    mock_config_entry.add_to_hass(hass)
    second_mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asdf"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_API_KEY: "asd"}
    mock_waqi.get_by_ip.assert_not_called()


@pytest.mark.parametrize(
    "api_key",
    [
        pytest.param("new_key", id="new_key"),
        pytest.param("asd", id="same_key"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    api_key: str,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    mock_waqi.authenticate.assert_called_with(api_key)


@pytest.mark.parametrize(
    "api_key",
    [
        pytest.param("new_key", id="new_key"),
        pytest.param("asd", id="same_key"),
    ],
)
async def test_reconfigure_flow_loaded_entry(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    api_key: str,
) -> None:
    """Test reconfiguring a loaded entry reloads it once."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await mock_config_entry.start_reconfigure_flow(hass)
    mock_waqi.get_by_station_number.reset_mock()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Each setup fetches the single station once, so one call means one reload
    mock_waqi.get_by_station_number.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIAuthenticationError("Test error"), "invalid_auth"),
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
    """Test reconfigure flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_waqi.get_by_ip.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_ip.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: "new_key"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_duplicate(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    second_mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring with the API key of another entry aborts."""
    mock_config_entry.add_to_hass(hass)
    second_mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "asdf"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_API_KEY: "asd"}
    mock_waqi.get_by_ip.assert_not_called()
