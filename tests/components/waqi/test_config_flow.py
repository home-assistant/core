"""Test the World Air Quality Index (WAQI) config flow."""
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from aiowaqi import WAQIAirQuality, WAQIAuthenticationError, WAQIConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.waqi.config_flow import CONF_MAP
from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_METHOD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import load_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        (
            CONF_MAP,
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
            },
        ),
        (
            CONF_STATION_NUMBER,
            {
                CONF_STATION_NUMBER: 4584,
            },
        ),
    ],
)
async def test_full_map_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    method: str,
    payload: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_ip",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "asd", CONF_METHOD: method},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == method

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_coordinates",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ), patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            payload,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {
        CONF_API_KEY: "asd",
        CONF_STATION_NUMBER: 4584,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WAQIAuthenticationError(), "invalid_auth"),
        (WAQIConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we handle errors during configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_ip",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "asd", CONF_METHOD: CONF_MAP},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_ip",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "asd", CONF_METHOD: CONF_MAP},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "map"

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_coordinates",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("method", "payload", "exception", "error"),
    [
        (
            CONF_MAP,
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
            },
            WAQIConnectionError(),
            "cannot_connect",
        ),
        (
            CONF_MAP,
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
            },
            Exception(),
            "unknown",
        ),
        (
            CONF_STATION_NUMBER,
            {
                CONF_STATION_NUMBER: 4584,
            },
            WAQIConnectionError(),
            "cannot_connect",
        ),
        (
            CONF_STATION_NUMBER,
            {
                CONF_STATION_NUMBER: 4584,
            },
            Exception(),
            "unknown",
        ),
    ],
)
async def test_error_in_second_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    method: str,
    payload: dict[str, Any],
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_ip",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "asd", CONF_METHOD: method},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == method

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_coordinates", side_effect=exception
    ), patch("aiowaqi.WAQIClient.get_by_station_number", side_effect=exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            payload,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(
        "aiowaqi.WAQIClient.authenticate",
    ), patch(
        "aiowaqi.WAQIClient.get_by_coordinates",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ), patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            payload,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {
        CONF_API_KEY: "asd",
        CONF_STATION_NUMBER: 4584,
    }
    assert len(mock_setup_entry.mock_calls) == 1
