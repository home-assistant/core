"""Test the Traccar Server config flow."""
from typing import Any
from unittest.mock import AsyncMock, patch

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


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.traccar_server.config_flow.ApiClient.get_server",
        return_value={"id": "1234"},
    ):
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
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    (
        (TraccarException, "cannot_connect"),
        (Exception, "unknown"),
    ),
)
async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.traccar_server.config_flow.ApiClient.get_server",
        side_effect=side_effect,
    ):
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

    with patch(
        "homeassistant.components.traccar_server.config_flow.ApiClient.get_server",
        return_value={"id": "1234"},
    ):
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
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert CONF_MAX_ACCURACY not in config_entry.options

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MAX_ACCURACY: 2.0},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
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
    mock_setup_entry: AsyncMock,
    imported: dict[str, Any],
    data: dict[str, Any],
    options: dict[str, Any],
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


async def test_abort_import_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
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
    mock_setup_entry: AsyncMock,
) -> None:
    """Test abort for existing server."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: "8082"},
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

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
