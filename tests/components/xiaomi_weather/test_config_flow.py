"""Exercise coordinate setup through HA's public flow manager."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from xiaomi_weather import Location, XiaomiWeatherError

from homeassistant.components.xiaomi_weather.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import LocationSelector

COORDINATES = {"latitude": 39.9, "longitude": 116.4}
BEIJING = Location("weathercn:101010100", "北京市", "中国", 39.9, 116.4, {})
CHAOYANG = Location("weathercn:101010300", "朝阳区", "北京市, 中国", 39.9, 116.4, {})


@pytest.mark.parametrize(
    "coordinates",
    [
        pytest.param(COORDINATES, id="beijing"),
        pytest.param({"latitude": 0.0, "longitude": 0.0}, id="zero"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    client: MagicMock,
    coordinates: dict[str, float],
) -> None:
    """Review the resolved city and supplied coordinates before saving."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema
    assert set(schema) == {"location"}
    assert isinstance(schema["location"], LocationSelector)
    assert schema["location"].config == {"radius": False}
    assert {key.schema: key.description["suggested_value"] for key in schema} == {
        "location": {
            "latitude": hass.config.latitude,
            "longitude": hass.config.longitude,
        },
    }
    client.locate.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": coordinates}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "city_name": "北京市",
        "city_id": "101010100",
        "latitude": str(coordinates["latitude"]),
        "longitude": str(coordinates["longitude"]),
    }
    client.get_weather.assert_not_awaited()
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
    client.locate.assert_awaited_once_with(
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
    client: MagicMock,
    failure: type[XiaomiWeatherError] | None,
    error: str,
) -> None:
    """Keep coordinates after a lookup failure and allow another attempt."""
    client.locate.return_value = []
    client.locate.side_effect = failure
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    assert result["data_schema"] is not None
    assert {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    } == {"location": COORDINATES}
    client.get_weather.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)
    client.locate.side_effect = None
    client.locate.return_value = [BEIJING]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "confirm"
    client.get_weather.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_weather_error_retry(hass: HomeAssistant, client: MagicMock) -> None:
    """Keep the location on the confirmation page until weather access succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "confirm"
    summary = result["description_placeholders"]
    client.get_weather.side_effect = XiaomiWeatherError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == summary
    assert not hass.config_entries.async_entries(DOMAIN)
    client.get_weather.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    client.locate.assert_awaited_once_with(39.9, 116.4)
    await hass.async_block_till_done()


async def test_multiple_matches(hass: HomeAssistant, client: MagicMock) -> None:
    """Review the selected city before saving an ambiguous match."""
    client.locate.return_value = [BEIJING, CHAOYANG]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "city"
    assert result["data_schema"] is not None
    assert result["data_schema"].schema["city_id"].config["options"] == [
        {"value": "101010100", "label": "北京市 · 中国 (101010100)"},
        {"value": "101010300", "label": "朝阳区 · 北京市, 中国 (101010300)"},
    ]
    client.get_weather.assert_not_awaited()
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
    client.get_weather.assert_not_awaited()
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
    client.locate.assert_awaited_once_with(39.9, 116.4)
    await hass.async_block_till_done()


async def test_duplicate(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Reject a city that is already configured before fetching weather."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.get_weather.assert_not_awaited()


async def test_duplicate_during_selection(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
) -> None:
    """Reject a city configured while the user was choosing a match."""
    client.locate.return_value = [BEIJING, CHAOYANG]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "city"
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"city_id": "101010100"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.get_weather.assert_not_awaited()


async def test_duplicate_during_confirmation(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Recheck duplicates when another entry is added during confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    assert result["step_id"] == "confirm"
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    client.get_weather.assert_not_awaited()


async def test_unsupported_current_temperature(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Require usable current temperature before accepting the confirmed city."""
    data = client.get_weather.return_value
    client.get_weather.return_value = replace(
        data,
        current=replace(
            data.current, temperature=replace(data.current.temperature, unit="F")
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": COORDINATES}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    assert not hass.config_entries.async_entries(DOMAIN)
    client.get_weather.return_value = data
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
