"""Test config flow for Nederlandse Spoorwegen integration."""

from datetime import time
from typing import Any
from unittest.mock import AsyncMock

import pytest
from requests import ConnectionError as RequestsConnectionError, HTTPError, Timeout

from homeassistant.components.nederlandse_spoorwegen.const import (
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import API_KEY

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_nsapi: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nederlandse Spoorwegen"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_creating_route(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a route after setting up the main config entry."""
    mock_config_entry.add_to_hass(hass)
    assert len(mock_config_entry.subentries) == 1
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "route"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_FROM: "ASD",
            CONF_TO: "RTD",
            CONF_VIA: "HT",
            CONF_NAME: "Home to Work",
            CONF_TIME: "08:30",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home to Work"
    assert result["data"] == {
        CONF_FROM: "ASD",
        CONF_TO: "RTD",
        CONF_VIA: "HT",
        CONF_NAME: "Home to Work",
        CONF_TIME: "08:30",
    }
    assert len(mock_config_entry.subentries) == 2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (HTTPError("Invalid API key"), "invalid_auth"),
        (Timeout("Cannot connect"), "cannot_connect"),
        (RequestsConnectionError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_flow_exceptions(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test config flow handling different exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_nsapi.get_stations.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_nsapi.get_stations.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nederlandse Spoorwegen"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_fetching_stations_failed(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a route after setting up the main config entry."""
    mock_config_entry.add_to_hass(hass)
    assert len(mock_config_entry.subentries) == 1
    mock_nsapi.get_stations.side_effect = RequestsConnectionError("Unexpected error")
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "route"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config flow aborts if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_import_success(
    hass: HomeAssistant, mock_nsapi: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful import flow from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nederlandse Spoorwegen"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert not result["result"].subentries


@pytest.mark.parametrize(
    ("routes_data", "expected_routes_data"),
    [
        (
            # Test with uppercase station codes (UI behavior)
            [
                {
                    CONF_NAME: "Home to Work",
                    CONF_FROM: "ASD",
                    CONF_TO: "RTD",
                    CONF_VIA: "HT",
                    CONF_TIME: time(hour=8, minute=30),
                }
            ],
            [
                {
                    CONF_NAME: "Home to Work",
                    CONF_FROM: "ASD",
                    CONF_TO: "RTD",
                    CONF_VIA: "HT",
                    CONF_TIME: time(hour=8, minute=30),
                }
            ],
        ),
        (
            # Test with lowercase station codes (converted to uppercase)
            [
                {
                    CONF_NAME: "Rotterdam-Amsterdam",
                    CONF_FROM: "rtd",  # lowercase input
                    CONF_TO: "asd",  # lowercase input
                },
                {
                    CONF_NAME: "Amsterdam-Haarlem",
                    CONF_FROM: "asd",  # lowercase input
                    CONF_TO: "ht",  # lowercase input
                    CONF_VIA: "rtd",  # lowercase input
                },
            ],
            [
                {
                    CONF_NAME: "Rotterdam-Amsterdam",
                    CONF_FROM: "RTD",  # converted to uppercase
                    CONF_TO: "ASD",  # converted to uppercase
                },
                {
                    CONF_NAME: "Amsterdam-Haarlem",
                    CONF_FROM: "ASD",  # converted to uppercase
                    CONF_TO: "HT",  # converted to uppercase
                    CONF_VIA: "RTD",  # converted to uppercase
                },
            ],
        ),
    ],
)
async def test_config_flow_import_with_routes(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_setup_entry: AsyncMock,
    routes_data: list[dict[str, Any]],
    expected_routes_data: list[dict[str, Any]],
) -> None:
    """Test import flow with routes from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_ROUTES: routes_data,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nederlandse Spoorwegen"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert len(result["result"].subentries) == len(expected_routes_data)

    subentries = list(result["result"].subentries.values())
    for expected_route in expected_routes_data:
        route_entry = next(
            entry for entry in subentries if entry.title == expected_route[CONF_NAME]
        )
        assert route_entry.data == expected_route
        assert route_entry.subentry_type == "route"


async def test_config_flow_import_with_unknown_station(
    hass: HomeAssistant, mock_nsapi: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow aborts with unknown station in routes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_ROUTES: [
                {
                    CONF_NAME: "Home to Work",
                    CONF_FROM: "HRM",
                    CONF_TO: "RTD",
                    CONF_VIA: "HT",
                    CONF_TIME: time(hour=8, minute=30),
                }
            ],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_station"


async def test_config_flow_import_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test import flow when integration is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (HTTPError("Invalid API key"), "invalid_auth"),
        (Timeout("Cannot connect"), "cannot_connect"),
        (RequestsConnectionError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_import_flow_exceptions(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test config flow handling different exceptions."""
    mock_nsapi.get_stations.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error
