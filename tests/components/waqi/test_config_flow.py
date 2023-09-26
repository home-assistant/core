"""Test the World Air Quality Index (WAQI) config flow."""
import json
from unittest.mock import AsyncMock, patch

from aiowaqi import WAQIAirQuality, WAQIAuthenticationError, WAQIConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import load_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

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
                CONF_API_KEY: "asd",
            },
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
        "aiowaqi.WAQIClient.get_by_coordinates",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
                CONF_API_KEY: "asd",
            },
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
                CONF_API_KEY: "asd",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
