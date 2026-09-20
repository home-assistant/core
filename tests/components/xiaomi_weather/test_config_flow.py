"""Exercise coordinate setup through HA's public flow manager."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xiaomi_weather.api import Location, XiaomiWeatherError
from homeassistant.components.xiaomi_weather.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

COORDINATES = {"latitude": 39.9, "longitude": 116.4}
BEIJING = Location("101010100", "北京市", "中国")
CHAOYANG = Location("101010300", "朝阳区", "北京市, 中国")


@pytest.fixture(autouse=True)
def locations() -> Generator[AsyncMock]:
    """Mock coordinate lookup without replacing the configuration flow."""
    with patch(
        "homeassistant.components.xiaomi_weather.config_flow.XiaomiLocationClient.async_locate",
        return_value=[BEIJING],
    ) as mock:
        yield mock


async def test_form(hass: HomeAssistant, locations: AsyncMock) -> None:
    """Only request coordinates, suggesting the Home Assistant location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema
    assert set(schema) == {"latitude", "longitude"}
    assert {key.schema: key.description["suggested_value"] for key in schema} == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
    }
    locations.assert_not_awaited()


@pytest.mark.parametrize(
    "coordinates",
    [
        pytest.param(COORDINATES, id="beijing"),
        pytest.param({"latitude": 0.0, "longitude": 0.0}, id="zero"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    client: AsyncMock,
    locations: AsyncMock,
    coordinates: dict[str, float],
) -> None:
    """Review the resolved city and supplied coordinates before saving."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=coordinates
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "city_name": "北京市",
        "city_id": "101010100",
        "latitude": str(coordinates["latitude"]),
        "longitude": str(coordinates["longitude"]),
    }
    client.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "北京市"
    assert result["data"] == {
        "name": "北京市",
        "city_id": "101010100",
        **coordinates,
    }
    assert result["result"].unique_id == "101010100"
    locations.assert_awaited_once_with(
        coordinates["latitude"], coordinates["longitude"]
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        pytest.param(None, "city_not_found", id="empty"),
        pytest.param(XiaomiWeatherError, "lookup_failed", id="failure"),
    ],
)
async def test_lookup_error_retry(
    hass: HomeAssistant,
    client: AsyncMock,
    locations: AsyncMock,
    failure: type[XiaomiWeatherError] | None,
    error: str,
) -> None:
    """Keep coordinates after a lookup failure and allow another attempt."""
    locations.return_value = []
    locations.side_effect = failure
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    assert result["data_schema"] is not None
    assert {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    } == COORDINATES
    client.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)
    locations.side_effect = None
    locations.return_value = [BEIJING]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], COORDINATES
    )
    assert result["step_id"] == "confirm"
    client.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_weather_error_retry(
    hass: HomeAssistant, client: AsyncMock, locations: AsyncMock
) -> None:
    """Keep the location on the confirmation page until weather access succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["step_id"] == "confirm"
    summary = result["description_placeholders"]
    client.side_effect = XiaomiWeatherError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == summary
    assert not hass.config_entries.async_entries(DOMAIN)
    client.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    locations.assert_awaited_once_with(39.9, 116.4)
    await hass.async_block_till_done()


async def test_multiple_matches(
    hass: HomeAssistant, client: AsyncMock, locations: AsyncMock
) -> None:
    """Review the selected city before saving an ambiguous match."""
    locations.return_value = [BEIJING, CHAOYANG]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["step_id"] == "city"
    assert result["data_schema"] is not None
    assert result["data_schema"].schema["city_id"].config["options"] == [
        {"value": "101010100", "label": "北京市 · 中国 (101010100)"},
        {"value": "101010300", "label": "朝阳区 · 北京市, 中国 (101010300)"},
    ]
    client.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"city_id": "101010300"}
    )
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "city_name": "朝阳区",
        "city_id": "101010300",
        "latitude": "39.9",
        "longitude": "116.4",
    }
    client.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "朝阳区"
    assert result["data"] == {
        "name": "朝阳区",
        "city_id": "101010300",
        **COORDINATES,
    }
    assert result["result"].unique_id == "101010300"
    locations.assert_awaited_once_with(39.9, 116.4)
    await hass.async_block_till_done()


async def test_duplicate(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Reject a city that is already configured before fetching weather."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.assert_not_awaited()


async def test_duplicate_during_selection(
    hass: HomeAssistant,
    client: AsyncMock,
    locations: AsyncMock,
    entry: MockConfigEntry,
) -> None:
    """Reject a city configured while the user was choosing a match."""
    locations.return_value = [BEIJING, CHAOYANG]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["step_id"] == "city"
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"city_id": "101010100"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.assert_not_awaited()


async def test_duplicate_during_confirmation(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Recheck duplicates when another entry is added during confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=COORDINATES
    )
    assert result["step_id"] == "confirm"
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.assert_not_awaited()
