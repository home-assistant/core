"""Test the Data Grand Lyon config flow."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientResponseError
from data_grand_lyon_ha import (
    VelovAvailabilityLevel,
    VelovBikeStandAvailability,
    VelovStation,
    VelovStationStatus,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.data_grandlyon.const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_VELOV_STATION = VelovStation(
    number=1002,
    name="Gare Part-Dieu",
    address="Place Charles Béraudier",
    commune="Lyon",
    status=VelovStationStatus.OPEN,
    availability=VelovAvailabilityLevel.GREEN,
    lat=45.76,
    lng=4.86,
    bike_stands=20,
    available_bikes=12,
    available_bike_stands=8,
    banking=True,
    last_update=datetime(2026, 4, 10, 12, 0),
    total_stands=VelovBikeStandAvailability(
        bikes=12,
        electrical_bikes=5,
        electrical_internal_battery_bikes=3,
        electrical_removable_battery_bikes=2,
        mechanical_bikes=7,
        stands=8,
        capacity=20,
    ),
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )


@pytest.fixture
def mock_config_entry_no_auth() -> MockConfigEntry:
    """Create a mock config entry without credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={},
    )


@pytest.fixture
def mock_config_entry_with_stop_subentry() -> MockConfigEntry:
    """Create a mock config entry with a stop subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={CONF_LINE: "C3", CONF_STOP_ID: 123},
                subentry_id="stop_1",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="C3 - Stop 123",
                unique_id="C3_123",
            )
        ],
    )


@pytest.fixture
def mock_config_entry_with_velov_subentry() -> MockConfigEntry:
    """Create a mock config entry with a Vélo'v subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={CONF_STATION_ID: 1002},
                subentry_id="velov_1",
                subentry_type=SUBENTRY_TYPE_VELOV,
                title="Gare Part-Dieu",
                unique_id="1002",
            )
        ],
    )


@pytest.fixture
def mock_config_entry_with_two_velov_subentries() -> MockConfigEntry:
    """Create a mock config entry with two Vélo'v subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={CONF_STATION_ID: 1002},
                subentry_id="velov_1",
                subentry_type=SUBENTRY_TYPE_VELOV,
                title="Gare Part-Dieu",
                unique_id="1002",
            ),
            config_entries.ConfigSubentryData(
                data={CONF_STATION_ID: 2001},
                subentry_id="velov_2",
                subentry_type=SUBENTRY_TYPE_VELOV,
                title="Bellecour",
                unique_id="2001",
            ),
        ],
    )


# Main config flow tests


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and can create an entry with credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Data Grand Lyon"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we can create an entry without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Data Grand Lyon"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we show an error when the API is unreachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect_no_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we show an error when the API is unreachable without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    # Second flow shows the form but aborts on submit
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring the main entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "new-user",
                CONF_PASSWORD: "new-pass",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "new-user",
        CONF_PASSWORD: "new-pass",
    }


async def test_reconfigure_remove_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring to remove credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {}


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure shows error when API is unreachable."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


# Stop subentry tests


async def test_stop_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test adding a stop subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3", CONF_STOP_ID: 456},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "C3 - Stop 456"
    assert result["data"] == {CONF_LINE: "C3", CONF_STOP_ID: 456}


async def test_stop_subentry_flow_with_custom_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test adding a stop subentry with a custom name."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "T1", CONF_STOP_ID: 789, CONF_NAME: "My Stop"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Stop"
    assert result["data"] == {CONF_LINE: "T1", CONF_STOP_ID: 789}


async def test_stop_subentry_aborts_without_auth(
    hass: HomeAssistant,
    mock_config_entry_no_auth: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test stop subentry aborts when no credentials are configured."""
    mock_config_entry_no_auth.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_no_auth.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_no_auth.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_required"


async def test_stop_subentry_reconfigure(
    hass: HomeAssistant,
    mock_config_entry_with_stop_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring a stop subentry."""
    mock_config_entry_with_stop_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop_subentry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry_with_stop_subentry.start_subentry_reconfigure_flow(
        hass, "stop_1"
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "T4", CONF_STOP_ID: 999, CONF_NAME: "Renamed Stop"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry_with_stop_subentry.subentries["stop_1"]
    assert subentry.data == {CONF_LINE: "T4", CONF_STOP_ID: 999}
    assert subentry.title == "Renamed Stop"


async def test_stop_subentry_reconfigure_default_name(
    hass: HomeAssistant,
    mock_config_entry_with_stop_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring a stop subentry without providing a name."""
    mock_config_entry_with_stop_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop_subentry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry_with_stop_subentry.start_subentry_reconfigure_flow(
        hass, "stop_1"
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "T4", CONF_STOP_ID: 999},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry_with_stop_subentry.subentries["stop_1"]
    assert subentry.title == "T4 - Stop 999"


# Vélo'v subentry tests


async def test_velov_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test adding a Vélo'v subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=MOCK_VELOV_STATION,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gare Part-Dieu"
    assert result["data"] == {CONF_STATION_ID: 1002}


async def test_velov_subentry_station_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v subentry with an invalid station ID."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV),
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 9999},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATION_ID: "station_not_found"}

    # Recover with a valid station
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=MOCK_VELOV_STATION,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gare Part-Dieu"


async def test_velov_subentry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v subentry when the API is unreachable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV),
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=MOCK_VELOV_STATION,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_velov_subentry_reconfigure(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring a Vélo'v subentry."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    new_station = VelovStation(
        number=2001,
        name="Bellecour",
        address="Place Bellecour",
        commune="Lyon",
        status=VelovStationStatus.OPEN,
        availability=VelovAvailabilityLevel.GREEN,
        lat=45.75,
        lng=4.83,
        bike_stands=30,
        available_bikes=20,
        available_bike_stands=10,
        banking=True,
        last_update=datetime(2026, 4, 10, 12, 0),
        total_stands=VelovBikeStandAvailability(
            bikes=20,
            electrical_bikes=10,
            electrical_internal_battery_bikes=5,
            electrical_removable_battery_bikes=5,
            mechanical_bikes=10,
            stands=10,
            capacity=30,
        ),
    )

    result = (
        await mock_config_entry_with_velov_subentry.start_subentry_reconfigure_flow(
            hass, "velov_1"
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=new_station,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 2001},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry_with_velov_subentry.subentries["velov_1"]
    assert subentry.data == {CONF_STATION_ID: 2001}
    assert subentry.title == "Bellecour"


async def test_velov_subentry_reconfigure_not_found(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring a Vélo'v subentry with invalid station."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = (
        await mock_config_entry_with_velov_subentry.start_subentry_reconfigure_flow(
            hass, "velov_1"
        )
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=None,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 9999},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATION_ID: "station_not_found"}


async def test_velov_subentry_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring a Vélo'v subentry when API fails."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = (
        await mock_config_entry_with_velov_subentry.start_subentry_reconfigure_flow(
            hass, "velov_1"
        )
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_stop_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry_with_stop_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test stop subentry aborts if same line+stop already exists."""
    mock_config_entry_with_stop_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop_subentry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_stop_subentry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3", CONF_STOP_ID: 123},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_velov_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v subentry aborts if same station already exists."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_velov_subentry.entry_id, SUBENTRY_TYPE_VELOV),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: 1002},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_velov_subentry_reconfigure_already_configured(
    hass: HomeAssistant,
    mock_config_entry_with_two_velov_subentries: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v reconfigure aborts if station_id collides with another subentry."""
    mock_config_entry_with_two_velov_subentries.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_two_velov_subentries.entry_id
    )
    await hass.async_block_till_done()

    # Reconfigure velov_2 (station 2001) to use station 1002 which is already velov_1
    result = await mock_config_entry_with_two_velov_subentries.start_subentry_reconfigure_flow(
        hass, "velov_2"
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: 1002},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_velov_subentry_reconfigure_same_station(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v reconfigure allows keeping the same station_id."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = (
        await mock_config_entry_with_velov_subentry.start_subentry_reconfigure_flow(
            hass, "velov_1"
        )
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        return_value=MOCK_VELOV_STATION,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


# Reauth tests


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauth flow with valid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
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


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauth flow when connection fails."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


# Error type differentiation tests


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we show invalid_auth on 401 response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientResponseError(None, None, status=401),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we show unknown on unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_http_error_non_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we show cannot_connect on non-auth HTTP errors (e.g. 500)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientResponseError(None, None, status=500),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_stop_subentry_reconfigure_collision(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test stop reconfigure aborts if new line+stop collides with another subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={CONF_LINE: "C3", CONF_STOP_ID: 123},
                subentry_id="stop_1",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="C3 - Stop 123",
                unique_id="C3_123",
            ),
            config_entries.ConfigSubentryData(
                data={CONF_LINE: "T1", CONF_STOP_ID: 456},
                subentry_id="stop_2",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="T1 - Stop 456",
                unique_id="T1_456",
            ),
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Reconfigure stop_2 to use C3/123 which is already stop_1
    result = await entry.start_subentry_reconfigure_flow(hass, "stop_2")

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3", CONF_STOP_ID: 123},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_velov_subentry_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v subentry shows unknown on unexpected exceptions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_VELOV),
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 9999},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_velov_subentry_reconfigure_unknown_error(
    hass: HomeAssistant,
    mock_config_entry_with_velov_subentry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Vélo'v reconfigure shows unknown on unexpected exceptions."""
    mock_config_entry_with_velov_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_velov_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = (
        await mock_config_entry_with_velov_subentry.start_subentry_reconfigure_flow(
            hass, "velov_1"
        )
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_velov_station",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: 1002},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
