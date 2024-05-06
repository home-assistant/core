"""Test the Traccar Server config flow."""
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytraccar import TraccarException

from homeassistant import config_entries
from homeassistant.components.traccar.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.traccar_server.const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_EVENTS,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_FILTER_FOR,
    DOMAIN,
    EVENTS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1:8082"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: "8082",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].state == config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "error"),
    (
        (TraccarException, "cannot_connect"),
        (Exception, "unknown"),
    ),
)
async def test_form_cannot_connect(
    hass: HomeAssistant,
    side_effect: Exception,
    error: str,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_traccar_api_client.get_server.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_traccar_api_client.get_server.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1:8082"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: "8082",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    assert result["result"].state == config_entries.ConfigEntryState.LOADED


async def test_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.options.get(CONF_MAX_ACCURACY) == 5.0

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MAX_ACCURACY: 2.0},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MAX_ACCURACY: 2.0,
        CONF_EVENTS: [],
        CONF_CUSTOM_ATTRIBUTES: [],
        CONF_SKIP_ACCURACY_FILTER_FOR: [],
    }


@pytest.mark.parametrize(
    ("imported", "data", "options"),
    (
        (
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: True,
                CONF_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
            {
                CONF_EVENTS: [],
                CONF_CUSTOM_ATTRIBUTES: [],
                CONF_SKIP_ACCURACY_FILTER_FOR: [],
                CONF_MAX_ACCURACY: 0,
            },
        ),
        (
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: True,
                "event": ["device_online", "device_offline"],
            },
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: "8082",
                CONF_VERIFY_SSL: True,
                CONF_SSL: True,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
            {
                CONF_EVENTS: ["device_online", "device_offline"],
                CONF_CUSTOM_ATTRIBUTES: [],
                CONF_SKIP_ACCURACY_FILTER_FOR: [],
                CONF_MAX_ACCURACY: 0,
            },
        ),
        (
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: True,
                "event": ["device_online", "device_offline", "all_events"],
            },
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: "8082",
                CONF_VERIFY_SSL: True,
                CONF_SSL: True,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
            {
                CONF_EVENTS: list(EVENTS.values()),
                CONF_CUSTOM_ATTRIBUTES: [],
                CONF_SKIP_ACCURACY_FILTER_FOR: [],
                CONF_MAX_ACCURACY: 0,
            },
        ),
    ),
)
async def test_import_from_yaml(
    hass: HomeAssistant,
    imported: dict[str, Any],
    data: dict[str, Any],
    options: dict[str, Any],
    mock_traccar_api_client: Generator[AsyncMock, None, None],
) -> None:
    """Test importing configuration from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=PLATFORM_SCHEMA({"platform": "traccar", **imported}),
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{data[CONF_HOST]}:{data[CONF_PORT]}"
    assert result["data"] == data
    assert result["options"] == options
    assert result["result"].state == config_entries.ConfigEntryState.LOADED


async def test_abort_import_already_configured(hass: HomeAssistant) -> None:
    """Test abort for existing server while importing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: "8082"},
    )

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=PLATFORM_SCHEMA(
            {
                "platform": "traccar",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_HOST: "1.1.1.1",
                CONF_PORT: "8082",
            }
        ),
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
) -> None:
    """Test abort for existing server."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: "8082",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
