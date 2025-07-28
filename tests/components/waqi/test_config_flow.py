"""Test the World Air Quality Index (WAQI) config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiowaqi import WAQIAuthenticationError, WAQIConnectionError
import pytest

from homeassistant.components.waqi.config_flow import CONF_MAP
from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_METHOD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


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
    mock_waqi: AsyncMock,
    method: str,
    payload: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "asd", CONF_METHOD: method},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == method

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        payload,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {
        CONF_API_KEY: "asd",
        CONF_STATION_NUMBER: 4584,
    }
    assert result["result"].unique_id == "4584"
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
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_waqi: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors during configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_waqi.get_by_ip.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "asd", CONF_METHOD: CONF_MAP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_ip.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "asd", CONF_METHOD: CONF_MAP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {CONF_LATITUDE: 50.0, CONF_LONGITUDE: 10.0},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    mock_waqi: AsyncMock,
    method: str,
    payload: dict[str, Any],
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "asd", CONF_METHOD: method},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == method

    mock_waqi.get_by_coordinates.side_effect = exception
    mock_waqi.get_by_station_number.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        payload,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_waqi.get_by_coordinates.side_effect = None
    mock_waqi.get_by_station_number.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        payload,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "de Jongweg, Utrecht"
    assert result["data"] == {
        CONF_API_KEY: "asd",
        CONF_STATION_NUMBER: 4584,
    }
    assert len(mock_setup_entry.mock_calls) == 1
