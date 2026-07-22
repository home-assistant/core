"""Test the Data Grand Lyon config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_PARK_ID,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_PARK_AND_RIDE,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Main config flow tests


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test we get the form and can create an entry with credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Data Grand Lyon"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ClientConnectionError(), "cannot_connect"),
        (ClientResponseError(None, None, status=401), "invalid_auth"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
    ids=["connection-error", "auth-401", "http-500", "unknown"],
)
async def test_form_error_recovers(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we show an error on API failures and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_tcl_client.get_tcl_passages.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Recover
    mock_tcl_client.get_tcl_passages.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the reauth flow updates credentials on success."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "new-user",
        CONF_PASSWORD: "new-pass",
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ClientConnectionError(), "cannot_connect"),
        (ClientResponseError(None, None, status=401), "invalid_auth"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
    ids=["connection-error", "auth-401", "http-500", "unknown"],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the reauth flow shows errors and recovers."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_tcl_client.get_tcl_passages.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_tcl_client.get_tcl_passages.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "new-user",
        CONF_PASSWORD: "new-pass",
    }


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the reconfigure flow updates credentials and preserves subentries."""
    mock_config_entry.add_to_hass(hass)
    original_subentries = dict(mock_config_entry.subentries)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "new-pass",
    }
    assert dict(mock_config_entry.subentries) == original_subentries


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ClientConnectionError(), "cannot_connect"),
        (ClientResponseError(None, None, status=401), "invalid_auth"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
    ids=["connection-error", "auth-401", "http-500", "unknown"],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the reconfigure flow shows errors and recovers."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_tcl_client.get_tcl_passages.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_tcl_client.get_tcl_passages.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "new-pass",
    }


# Stop subentry tests


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_stop_subentry_picker_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a stop subentry by picking a stop and a line from the lists."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert mock_tcl_client.get_tcl_stops.await_count == 1

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "200"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_line"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "T1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "T1 - Stop 200"
    assert result["data"] == {CONF_LINE: "T1", CONF_STOP_ID: 200}
    assert result["unique_id"] == "T1_200"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_stop_subentry_custom_value_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a stop subentry by typing a stop ID not present in the list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "456"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_line"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "C3 - Stop 456"
    assert result["data"] == {CONF_LINE: "C3", CONF_STOP_ID: 456}
    assert result["unique_id"] == "C3_456"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_stop_subentry_invalid_stop_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a non-numeric stop ID re-renders the form with an error and recovers."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "not-a-number"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_STOP_ID: "invalid_stop_id"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "200"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_line"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "T1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "T1 - Stop 200"
    assert result["data"] == {CONF_LINE: "T1", CONF_STOP_ID: 200}
    assert result["unique_id"] == "T1_200"


async def test_stop_subentry_picker_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test picker stop subentry aborts if same line+stop already exists."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "100"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (
            ClientResponseError(request_info=None, history=(), status=500),
            "cannot_connect",
        ),
        (
            ClientResponseError(request_info=None, history=(), status=401),
            "invalid_auth",
        ),
        (ClientConnectionError("boom"), "cannot_connect"),
        (TimeoutError("boom"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
@pytest.mark.parametrize("mock_subentries", [[]])
async def test_stop_subentry_picker_load_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test picker aborts with the right reason when loading stops fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tcl_client.get_tcl_stops.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


# Vélo'v station subentry tests


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_velov_station_subentry_picker_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a Vélo'v station subentry by picking a station from the list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert mock_tcl_client.get_velov_stations.await_count == 1

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "1001"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vélo'v 1001"
    assert result["data"] == {CONF_STATION_ID: 1001}
    assert result["unique_id"] == "velov_1001"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_velov_station_subentry_custom_value_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a Vélo'v station subentry by typing an ID not present in the list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "3003"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vélo'v 3003"
    assert result["data"] == {CONF_STATION_ID: 3003}
    assert result["unique_id"] == "velov_3003"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_velov_station_subentry_invalid_station_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a non-numeric station ID re-renders the form with an error and recovers."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "not-a-number"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_STATION_ID: "invalid_station_id"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "1001"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vélo'v 1001"
    assert result["data"] == {CONF_STATION_ID: 1001}
    assert result["unique_id"] == "velov_1001"


async def test_velov_station_subentry_already_configured(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v station subentry aborts if same station already exists."""
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_velov_config_entry.entry_id, SUBENTRY_TYPE_VELOV_STATION),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "1001"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (
            ClientResponseError(request_info=None, history=(), status=500),
            "cannot_connect",
        ),
        (
            ClientResponseError(request_info=None, history=(), status=401),
            "invalid_auth",
        ),
        (ClientConnectionError("boom"), "cannot_connect"),
        (TimeoutError("boom"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
@pytest.mark.parametrize("mock_subentries", [[]])
async def test_velov_station_subentry_picker_load_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test picker aborts with the right reason when loading stations fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tcl_client.get_velov_stations.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV_STATION),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


# Park-and-ride subentry tests


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_park_and_ride_subentry_picker_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a park-and-ride subentry by picking one from the list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARK_AND_RIDE),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert mock_tcl_client.get_tcl_park_and_rides.await_count == 1

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PARK_ID: "P+R Gorge de Loup"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gorge de Loup"
    assert result["data"] == {CONF_PARK_ID: "P+R Gorge de Loup"}
    assert result["unique_id"] == "park_and_ride_P+R Gorge de Loup"


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_park_and_ride_subentry_custom_value_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test adding a park-and-ride by typing an ID not present in the list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARK_AND_RIDE),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PARK_ID: "P+R Unknown"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "P+R Unknown"
    assert result["data"] == {CONF_PARK_ID: "P+R Unknown"}
    assert result["unique_id"] == "park_and_ride_P+R Unknown"


async def test_park_and_ride_subentry_already_configured(
    hass: HomeAssistant,
    mock_park_and_ride_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test park-and-ride subentry aborts if same facility already exists."""
    mock_park_and_ride_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_park_and_ride_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_park_and_ride_config_entry.entry_id, SUBENTRY_TYPE_PARK_AND_RIDE),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PARK_ID: "P+R Gorge de Loup"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (
            ClientResponseError(request_info=None, history=(), status=500),
            "cannot_connect",
        ),
        (
            ClientResponseError(request_info=None, history=(), status=401),
            "invalid_auth",
        ),
        (ClientConnectionError("boom"), "cannot_connect"),
        (TimeoutError("boom"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
@pytest.mark.parametrize("mock_subentries", [[]])
async def test_park_and_ride_subentry_picker_load_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test picker aborts with the right reason when loading park-and-rides fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tcl_client.get_tcl_park_and_rides.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARK_AND_RIDE),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
