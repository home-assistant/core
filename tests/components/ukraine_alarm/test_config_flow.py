"""Test the Ukraine Alarm config flow."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.ukraine_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _region(rid, recurse=0, depth=0):
    if depth == 0:
        name_prefix = "State"
    elif depth == 1:
        name_prefix = "District"
    else:
        name_prefix = "Community"

    name = f"{name_prefix} {rid}"
    region = {"regionId": rid, "regionName": name, "regionChildIds": []}

    if not recurse:
        return region

    for i in range(1, 4):
        region["regionChildIds"].append(_region(f"{rid}.{i}", recurse - 1, depth + 1))

    return region


REGIONS = {
    "states": [_region(f"{i}", i - 1) for i in range(1, 4)],
}


@pytest.fixture(autouse=True)
def mock_get_regions() -> Generator[None, AsyncMock, None]:
    """Mock the get_regions method."""

    with patch(
        "homeassistant.components.ukraine_alarm.config_flow.Client.get_regions",
        return_value=REGIONS,
    ) as mock_get:
        yield mock_get


async def test_state(hass: HomeAssistant) -> None:
    """Test we can create entry for state."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.ukraine_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "region": "1",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "State 1"
    assert result3["data"] == {
        "region": "1",
        "name": result3["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district(hass: HomeAssistant) -> None:
    """Test we can create entry for state + district."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] == FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "2",
        },
    )
    assert result3["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.ukraine_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "region": "2.2",
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "District 2.2"
    assert result4["data"] == {
        "region": "2.2",
        "name": result4["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district_pick_region(hass: HomeAssistant) -> None:
    """Test we can create entry for region which has districts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] == FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "2",
        },
    )
    assert result3["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.ukraine_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "region": "2",
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "State 2"
    assert result4["data"] == {
        "region": "2",
        "name": result4["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district_community(hass: HomeAssistant) -> None:
    """Test we can create entry for state + district + community."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
    )
    assert result2["type"] == FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "3",
        },
    )
    assert result3["type"] == FlowResultType.FORM

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "3.2",
        },
    )
    assert result4["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.ukraine_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "region": "3.2.1",
            },
        )
        await hass.async_block_till_done()

    assert result5["type"] == FlowResultType.CREATE_ENTRY
    assert result5["title"] == "Community 3.2.1"
    assert result5["data"] == {
        "region": "3.2.1",
        "name": result5["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_max_regions(hass: HomeAssistant) -> None:
    """Test max regions config."""
    for i in range(5):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=i,
        ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "max_regions"


async def test_rate_limit(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test rate limit error."""
    mock_get_regions.side_effect = ClientResponseError(None, None, status=429)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "rate_limit"


async def test_server_error(hass: HomeAssistant, mock_get_regions) -> None:
    """Test server error."""
    mock_get_regions.side_effect = ClientResponseError(
        RequestInfo(None, None, None, real_url=URL("/regions")), None, status=500
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_cannot_connect(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test connection error."""
    mock_get_regions.side_effect = ClientConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_unknown_client_error(
    hass: HomeAssistant, mock_get_regions: AsyncMock
) -> None:
    """Test client error."""
    mock_get_regions.side_effect = ClientError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_timeout_error(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test timeout error."""
    mock_get_regions.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout"


async def test_no_regions_returned(
    hass: HomeAssistant, mock_get_regions: AsyncMock
) -> None:
    """Test regions not returned."""
    mock_get_regions.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"
