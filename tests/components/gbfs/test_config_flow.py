"""Tests for the GBFS config flow."""

from collections.abc import Callable

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_fixture,
    get_schema_suggested_value,
    load_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gbfs.const import (
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MIRROR_URL, V2_URL, V3_URL, mock_feed


@pytest.mark.usefixtures("mock_v3_feed", "mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test adding a system by its discovery URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: V3_URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Example Bikes"
    assert result["data"] == {CONF_URL: V3_URL}
    assert result["result"].unique_id == "example_bikes"


def _serve_dockless(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(
        V3_URL,
        json={
            "version": "3.0",
            "ttl": 0,
            "last_updated": "2026-11-05T12:00:00Z",
            "data": {
                "feeds": [
                    {
                        "name": "system_information",
                        "url": "https://gbfs.example.com/v3/system_information.json",
                    },
                    {
                        "name": "vehicle_status",
                        "url": "https://gbfs.example.com/v3/vehicle_status.json",
                    },
                ]
            },
        },
    )
    aioclient_mock.get(
        "https://gbfs.example.com/v3/system_information.json",
        text=load_fixture("v3/system_information.json", DOMAIN),
    )


@pytest.mark.parametrize(
    ("url", "serve", "error"),
    [
        pytest.param(
            "http://[::1",
            lambda m: None,
            "invalid_url",
            id="malformed_url",
        ),
        pytest.param(
            "ftp://gbfs.example.com/gbfs.json",
            lambda m: None,
            "invalid_url",
            id="invalid_url",
        ),
        pytest.param(
            V3_URL,
            lambda m: m.get(V3_URL, exc=ClientError()),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            V3_URL,
            lambda m: m.get(V3_URL, text="not json"),
            "invalid_feed",
            id="invalid_feed",
        ),
        pytest.param(V3_URL, _serve_dockless, "no_stations", id="no_stations"),
        pytest.param(
            V3_URL, lambda m: m.get(V3_URL, exc=RuntimeError()), "unknown", id="unknown"
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    url: str,
    serve: Callable[[AiohttpClientMocker], None],
    error: str,
) -> None:
    """Test errors are shown and the flow recovers."""
    serve(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    mock_feed(aioclient_mock, "v3")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: V3_URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_v3_feed", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a system can only be added once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: V3_URL}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_v3_feed", "mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test moving a system to a new discovery URL."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(
        MIRROR_URL,
        text=await async_load_fixture(hass, "v3/gbfs.json", DOMAIN),
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_URL) == V3_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: MIRROR_URL}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_URL: MIRROR_URL}


@pytest.mark.usefixtures("mock_v3_feed", "mock_setup_entry")
async def test_reconfigure_other_system(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a URL for a different system is refused."""
    mock_config_entry.add_to_hass(hass)
    mock_feed(aioclient_mock, "v2")
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: V2_URL}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_URL: V3_URL}


@pytest.mark.usefixtures("init_integration")
async def test_add_station(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test stations are offered closest first and added as subentries."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STATION),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_STATION_ID].config["options"]
    assert [option["value"] for option in options] == ["s1", "s2", "s3"]
    assert options[0]["label"] == "Main St & 1st Ave (0.0 km)"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATION_ID: "s2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Park Ave & 2nd St"
    assert result["data"] == {CONF_STATION_ID: "s2"}
    assert result["unique_id"] == "s2"


@pytest.mark.usefixtures("init_integration")
async def test_add_station_already_added(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a station can only be added once."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STATION),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATION_ID: "s1"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_add_station_entry_not_loaded(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stations can't be added while the system isn't loaded."""
    aioclient_mock.get(V3_URL, exc=ClientError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STATION),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
