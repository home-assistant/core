"""Test the Ukraine Alarm config flow."""
import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.ukraine_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

MOCK_API_KEY = "mock-api-key"


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
    assert result["type"] == RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

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

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "State 1"
    assert result3["data"] == {
        "api_key": MOCK_API_KEY,
        "region": "1",
        "name": result3["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district(hass: HomeAssistant) -> None:
    """Test we can create entry for state + district."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "2",
        },
    )
    assert result3["type"] == RESULT_TYPE_FORM

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

    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result4["title"] == "District 2.2"
    assert result4["data"] == {
        "api_key": MOCK_API_KEY,
        "region": "2.2",
        "name": result4["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district_pick_region(hass: HomeAssistant) -> None:
    """Test we can create entry for region which has districts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "2",
        },
    )
    assert result3["type"] == RESULT_TYPE_FORM

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

    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result4["title"] == "State 2"
    assert result4["data"] == {
        "api_key": MOCK_API_KEY,
        "region": "2",
        "name": result4["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_state_district_community(hass: HomeAssistant) -> None:
    """Test we can create entry for state + district + community."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "3",
        },
    )
    assert result3["type"] == RESULT_TYPE_FORM

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "region": "3.2",
        },
    )
    assert result4["type"] == RESULT_TYPE_FORM

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

    assert result5["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result5["title"] == "Community 3.2.1"
    assert result5["data"] == {
        "api_key": MOCK_API_KEY,
        "region": "3.2.1",
        "name": result5["title"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_api(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.side_effect = ClientResponseError(None, None, status=401)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_api_key"}


async def test_server_error(hass: HomeAssistant, mock_get_regions) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.side_effect = ClientResponseError(None, None, status=500)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_cannot_connect(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.side_effect = ClientConnectionError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_unknown_client_error(
    hass: HomeAssistant, mock_get_regions: AsyncMock
) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.side_effect = ClientError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_timeout_error(hass: HomeAssistant, mock_get_regions: AsyncMock) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.side_effect = asyncio.TimeoutError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "timeout"}


async def test_no_regions_returned(
    hass: HomeAssistant, mock_get_regions: AsyncMock
) -> None:
    """Test we can create entry for just region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    mock_get_regions.return_value = {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": MOCK_API_KEY,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}
