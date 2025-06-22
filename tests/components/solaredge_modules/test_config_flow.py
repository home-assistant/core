"""Test the SolarEdge Modules config flow."""

from unittest.mock import AsyncMock

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge_modules.const import CONF_SITE_ID, DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SITE_ID: "123456",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_solar_edge_web.async_get_equipment.assert_awaited_once()


@pytest.mark.parametrize(
    ("api_exception", "expected_error"),
    [
        (aiohttp.ClientResponseError(None, None, status=401), "invalid_auth"),
        (aiohttp.ClientResponseError(None, None, status=403), "invalid_auth"),
        (aiohttp.ClientResponseError(None, None, status=400), "cannot_connect"),
        (aiohttp.ClientResponseError(None, None, status=500), "cannot_connect"),
        (aiohttp.ClientError(), "cannot_connect"),
        (ValueError(), "unknown"),
    ],
)
async def test_form_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_solar_edge_web: AsyncMock,
    api_exception,
    expected_error,
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_solar_edge_web.async_get_equipment.side_effect = api_exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    mock_solar_edge_web.async_get_equipment.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SITE_ID: "123456",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: mock_config_entry.data[CONF_SITE_ID],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_solar_edge_web.async_get_equipment.assert_not_called()


async def test_form_not_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test user input for config_entry different than the existing one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: "654321",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SITE_ID: "654321",
    }
    assert len(mock_setup_entry.mock_calls) == 2
    mock_solar_edge_web.async_get_equipment.assert_awaited_once()
