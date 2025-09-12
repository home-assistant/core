"""Test config flow for Nederlandse Spoorwegen integration."""

from datetime import time
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.nederlandse_spoorwegen.api import (
    NSAPIAuthError,
    NSAPIConnectionError,
)
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


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (NSAPIAuthError("Invalid API key"), "invalid_auth"),
        (NSAPIConnectionError("Cannot connect"), "cannot_connect"),
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


async def test_config_flow_import_with_routes(
    hass: HomeAssistant, mock_nsapi: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow with routes from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_ROUTES: [
                {
                    CONF_NAME: "Home to Work",
                    CONF_FROM: "ASD",
                    CONF_TO: "RTD",
                    CONF_VIA: "HT",
                    CONF_TIME: time(hour=8, minute=30),
                }
            ],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nederlandse Spoorwegen"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert len(result["result"].subentries) == 1
    route_entry = list(result["result"].subentries.values())[0]
    assert route_entry.data == {
        CONF_NAME: "Home to Work",
        CONF_FROM: "ASD",
        CONF_TO: "RTD",
        CONF_VIA: "HT",
        CONF_TIME: time(hour=8, minute=30),
    }
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
        (NSAPIAuthError("Invalid API key"), "invalid_auth"),
        (NSAPIConnectionError("Cannot connect"), "cannot_connect"),
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
