"""Test the mvglive config flow."""

from unittest.mock import AsyncMock

from mvg import MvgApiError
import pytest

from homeassistant.components.mvglive.const import (
    CONF_DESTINATIONS,
    CONF_DIRECTIONS,
    CONF_LINES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_STATION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TIMEOFFSET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import TEST_STATION

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mvg_api")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow with a single search match."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION: "Hauptbahnhof", CONF_PRODUCTS: ["U-Bahn"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION_ID: TEST_STATION["id"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_STATION["name"]
    assert result["result"].unique_id == TEST_STATION["id"]
    assert result["data"] == {
        CONF_STATION_ID: TEST_STATION["id"],
        CONF_STATION_NAME: TEST_STATION["name"],
    }
    assert result["options"] == {CONF_PRODUCTS: ["U-Bahn"]}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_multiple_matches_offers_a_choice(
    hass: HomeAssistant, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that multiple search matches are offered as a dropdown to pick from."""
    other_station = {"id": "de:09162:5", "name": "Ostbahnhof", "place": "München"}
    mvg_api["stations_async"].return_value = [TEST_STATION, other_station]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION: "bahnhof"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    options = result["data_schema"].schema[CONF_STATION_ID].config["options"]
    assert {option["value"] for option in options} == {
        TEST_STATION["id"],
        other_station["id"],
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION_ID: other_station["id"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == other_station["name"]
    assert result["data"] == {
        CONF_STATION_ID: other_station["id"],
        CONF_STATION_NAME: other_station["name"],
    }


async def test_invalid_station(
    hass: HomeAssistant, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that a search with no matches shows an error."""
    mvg_api["stations_async"].return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION: "Nonexistent"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_station"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_cannot_connect(
    hass: HomeAssistant, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that an API failure while searching shows an error, and that it can be retried."""
    mvg_api["stations_async"].side_effect = MvgApiError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION: "Hauptbahnhof"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mvg_api["stations_async"].side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION: "Hauptbahnhof"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION_ID: TEST_STATION["id"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_STATION["id"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that an API failure while importing YAML aborts, and that a retry succeeds."""
    mvg_api["station_async"].side_effect = MvgApiError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION: "Hauptbahnhof"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mvg_api["station_async"].side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION: "Hauptbahnhof"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_STATION["id"]


@pytest.mark.usefixtures("mock_setup_entry", "mvg_api")
async def test_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test aborting when the picked station is already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION: "Hauptbahnhof"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STATION_ID: TEST_STATION["id"]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mvg_api")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing a legacy YAML `nextdeparture` entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION: "Hauptbahnhof",
            CONF_DESTINATIONS: ["Feldmoching"],
            CONF_LINES: ["U2"],
            CONF_TIMEOFFSET: 5,
            CONF_NUMBER: 3,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_STATION["name"]
    assert result["result"].unique_id == TEST_STATION["id"]
    assert result["data"] == {
        CONF_STATION_ID: TEST_STATION["id"],
        CONF_STATION_NAME: TEST_STATION["name"],
    }
    assert result["options"] == {
        CONF_DESTINATIONS: ["Feldmoching"],
        CONF_LINES: ["U2"],
        CONF_PRODUCTS: None,
        CONF_TIMEOFFSET: 5,
        CONF_NUMBER: 3,
    }


@pytest.mark.usefixtures("mock_setup_entry", "mvg_api")
async def test_import_flow_legacy_directions(hass: HomeAssistant) -> None:
    """Test that a legacy `directions` entry is imported as `destinations`."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION: "Hauptbahnhof",
            CONF_DIRECTIONS: ["Feldmoching"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_DESTINATIONS] == ["Feldmoching"]


@pytest.mark.usefixtures("mock_setup_entry", "mvg_api")
async def test_import_flow_multiple_entries_same_station(hass: HomeAssistant) -> None:
    """Test importing two `nextdeparture` entries for the same station by name."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION: "Hauptbahnhof", CONF_NAME: "To Feldmoching"},
    )
    await hass.async_block_till_done()
    assert first["type"] is FlowResultType.CREATE_ENTRY
    assert first["title"] == "To Feldmoching"

    second = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION: "Hauptbahnhof", CONF_NAME: "To Ostbahnhof"},
    )
    await hass.async_block_till_done()

    assert second["type"] is FlowResultType.CREATE_ENTRY
    assert second["title"] == "To Ostbahnhof"
    assert second["result"].unique_id != first["result"].unique_id


async def test_import_flow_invalid_station(
    hass: HomeAssistant, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that importing an unresolvable station aborts."""
    mvg_api["station_async"].return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION: "Nonexistent"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_station"


@pytest.mark.usefixtures("mvg_api")
async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the options flow."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DESTINATIONS: ["Feldmoching", "Messestadt Ost"],
            CONF_LINES: ["U2", "U8"],
            CONF_TIMEOFFSET: 5,
            CONF_NUMBER: 3,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DESTINATIONS: ["Feldmoching", "Messestadt Ost"],
        CONF_LINES: ["U2", "U8"],
        CONF_PRODUCTS: [],
        CONF_TIMEOFFSET: 5,
        CONF_NUMBER: 3,
    }
