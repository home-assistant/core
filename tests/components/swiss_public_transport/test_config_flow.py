"""Test the swiss_public_transport config flow."""

from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_STATIONS,
    CONF_STOPS_AT,
    CONF_TIME_FIXED,
    CONF_TIME_MODE,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    DOMAIN,
    MAX_STATIONS,
    MAX_VIA,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_USER_DATA_STEP = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
    CONF_TIME_STATION: "departure",
    CONF_TIME_MODE: "now",
}

MOCK_USER_DATA_STEP_ONE_VIA = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: ["via_station"],
}

MOCK_USER_DATA_STEP_MANY_VIA = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: ["via_station_1", "via_station_2", "via_station_3"],
}

MOCK_USER_DATA_STEP_TOO_MANY_STATIONS = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: MOCK_USER_DATA_STEP_ONE_VIA[CONF_VIA] * (MAX_VIA + 1),
}

MOCK_USER_DATA_STEP_ONE_TRANSPORTATION = {
    **MOCK_USER_DATA_STEP,
    CONF_TRANSPORTATIONS: ["train"],
}

MOCK_USER_DATA_STEP_MANY_TRANSPORTATIONS = {
    **MOCK_USER_DATA_STEP_ONE_VIA,
    CONF_TRANSPORTATIONS: ["train", "bus"],
}

MOCK_USER_DATA_STEP_ARRIVAL = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_STATION: "arrival",
}

MOCK_USER_DATA_STEP_TIME_FIXED = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "fixed",
}

MOCK_USER_DATA_STEP_TIME_FIXED_OFFSET = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "offset",
}

MOCK_USER_DATA_STEP_BAD = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "bad",
}

MOCK_ADVANCED_DATA_STEP_TIME = {
    CONF_TIME_FIXED: "18:03:00",
}

MOCK_ADVANCED_DATA_STEP_TIME_OFFSET = {
    CONF_TIME_OFFSET: {"hours": 0, "minutes": 10, "seconds": 0},
}


@pytest.mark.parametrize(
    ("user_input", "time_mode_input", "config_title"),
    [
        (MOCK_USER_DATA_STEP, None, "test_start test_destination"),
        (
            MOCK_USER_DATA_STEP_ONE_VIA,
            None,
            "test_start test_destination via via_station",
        ),
        (
            MOCK_USER_DATA_STEP_MANY_VIA,
            None,
            "test_start test_destination via"
            " via_station_1, via_station_2, via_station_3",
        ),
        (
            MOCK_USER_DATA_STEP_ONE_TRANSPORTATION,
            None,
            "test_start test_destination by train",
        ),
        (
            MOCK_USER_DATA_STEP_MANY_TRANSPORTATIONS,
            None,
            "test_start test_destination via via_station by bus, train",
        ),
        (MOCK_USER_DATA_STEP_ARRIVAL, None, "test_start test_destination arrival"),
        (
            MOCK_USER_DATA_STEP_TIME_FIXED,
            MOCK_ADVANCED_DATA_STEP_TIME,
            "test_start test_destination at 18:03:00",
        ),
        (
            MOCK_USER_DATA_STEP_TIME_FIXED_OFFSET,
            MOCK_ADVANCED_DATA_STEP_TIME_OFFSET,
            "test_start test_destination in 00:10:00",
        ),
    ],
)
async def test_flow_user_init_data_success(
    hass: HomeAssistant, user_input, time_mode_input, config_title
) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "connection"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.USER_DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        if time_mode_input:
            assert result["type"] is FlowResultType.FORM
            if CONF_TIME_FIXED in time_mode_input:
                assert result["step_id"] == "time_fixed"
            if CONF_TIME_OFFSET in time_mode_input:
                assert result["step_id"] == "time_offset"
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=time_mode_input,
            )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == config_title

        assert result["data"] == {**user_input, **(time_mode_input or {})}
        assert result["result"].unique_id == config_title


@pytest.mark.parametrize(
    ("raise_error", "text_error", "user_input_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect", MOCK_USER_DATA_STEP),
        (OpendataTransportError(), "bad_config", MOCK_USER_DATA_STEP),
        (None, "too_many_via_stations", MOCK_USER_DATA_STEP_TOO_MANY_STATIONS),
        (IndexError(), "unknown", MOCK_USER_DATA_STEP),
    ],
)
async def test_flow_user_init_data_error_and_recover_on_step_1(
    hass: HomeAssistant, raise_error, text_error, user_input_error
) -> None:
    """Test errors in user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "connection"}
    )
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input_error,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_USER_DATA_STEP


@pytest.mark.parametrize(
    ("raise_error", "text_error", "user_input"),
    [
        (
            OpendataTransportConnectionError(),
            "cannot_connect",
            MOCK_ADVANCED_DATA_STEP_TIME,
        ),
        (OpendataTransportError(), "bad_config", MOCK_ADVANCED_DATA_STEP_TIME),
        (IndexError(), "unknown", MOCK_ADVANCED_DATA_STEP_TIME),
    ],
)
async def test_flow_user_init_data_error_and_recover_on_step_2(
    hass: HomeAssistant, raise_error, text_error, user_input
) -> None:
    """Test errors in time mode step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "connection"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.USER_DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_DATA_STEP_TIME_FIXED,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "time_fixed"

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination at 18:03:00"


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA_STEP,
        unique_id=unique_id_from_config(MOCK_USER_DATA_STEP),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "connection"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_DATA_STEP,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("user_input", "stops_at", "config_title"),
    [
        pytest.param(
            {CONF_STATIONS: ["Zürich HB"]}, [], "Zürich HB", id="single_station"
        ),
        pytest.param(
            {CONF_STATIONS: ["Kriens, Mattenhof", "Kriens Mattenhof"]},
            [],
            "Kriens, Mattenhof, Kriens Mattenhof",
            id="multiple_stations",
        ),
        pytest.param(
            {CONF_STATIONS: ["Zürich HB"], CONF_STOPS_AT: ["zug"]},
            ["Zug"],
            "Zürich HB stops at Zug",
            id="stops_at",
        ),
    ],
)
@pytest.mark.usefixtures("mock_stationboard_client", "mock_location_client")
async def test_flow_stationboard_success(
    hass: HomeAssistant,
    user_input: dict[str, list[str]],
    stops_at: list[str],
    config_title: str,
) -> None:
    """Test setting up a stationboard."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "stationboard"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stationboard"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == config_title
    assert result["data"] == {**user_input, CONF_STOPS_AT: stops_at}
    assert result["result"].unique_id == f"stationboard {config_title}"


@pytest.mark.parametrize(
    ("raise_error", "journeys", "stations", "text_error"),
    [
        pytest.param(
            OpendataTransportConnectionError(),
            [],
            ["Zürich HB"],
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            OpendataTransportError(), [], ["Zürich HB"], "bad_config", id="bad_data"
        ),
        pytest.param(IndexError(), [], ["Zürich HB"], "unknown", id="unknown"),
        pytest.param(None, [], ["Zürich HB"], "bad_config", id="unknown_station"),
        pytest.param(None, [], [], "bad_config", id="no_station"),
        pytest.param(
            None,
            [{"departure": "2024-01-06T18:03:00+0100"}],
            ["Zürich HB"] * (MAX_STATIONS + 1),
            "too_many_stations",
            id="too_many_stations",
        ),
    ],
)
async def test_flow_stationboard_error_and_recover(
    hass: HomeAssistant,
    mock_stationboard_client: AsyncMock,
    raise_error: Exception | None,
    journeys: list[dict[str, str]],
    stations: list[str],
    text_error: str,
) -> None:
    """Test errors in the stationboard step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "stationboard"}
    )

    valid_journeys = mock_stationboard_client.journeys
    mock_stationboard_client.async_get_data.side_effect = raise_error
    mock_stationboard_client.journeys = journeys
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATIONS: stations}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_stationboard_client.async_get_data.side_effect = None
    mock_stationboard_client.journeys = valid_journeys
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATIONS: ["Zürich HB"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_STATIONS: ["Zürich HB"], CONF_STOPS_AT: []}


@pytest.mark.parametrize(
    ("raise_error", "locations", "text_error"),
    [
        pytest.param(
            OpendataTransportConnectionError(),
            [],
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(OpendataTransportError(), [], "bad_config", id="bad_data"),
        pytest.param(IndexError(), [], "unknown", id="unknown"),
        pytest.param(None, [], "bad_config", id="unknown_station"),
    ],
)
@pytest.mark.usefixtures("mock_stationboard_client")
async def test_flow_stationboard_stops_at_error_and_recover(
    hass: HomeAssistant,
    mock_location_client: AsyncMock,
    raise_error: Exception | None,
    locations: list[dict[str, str]],
    text_error: str,
) -> None:
    """Test errors looking up the stations a departure must stop at."""
    user_input = {CONF_STATIONS: ["Zürich HB"], CONF_STOPS_AT: ["Zug"]}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "stationboard"}
    )

    valid_locations = mock_location_client.locations
    mock_location_client.async_get_data.side_effect = raise_error
    mock_location_client.locations = locations
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_location_client.async_get_data.side_effect = None
    mock_location_client.locations = valid_locations
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input


@pytest.mark.usefixtures("mock_stationboard_client")
async def test_flow_stationboard_already_configured(
    hass: HomeAssistant, mock_stationboard_config_entry: MockConfigEntry
) -> None:
    """Test we abort when the stationboard is already configured."""
    mock_stationboard_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "stationboard"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_stationboard_config_entry.data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
