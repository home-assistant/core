"""Tests for the ZoneMinder config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    Timeout as RequestsTimeout,
)

from homeassistant.components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_PATH,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG_DATA, MOCK_HOST, MOCK_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant, mock_zoneminder_client: MagicMock
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG_DATA
    assert result["options"] == MOCK_OPTIONS
    mock_zoneminder_client.mock_cls.assert_called_once_with(
        f"http://{MOCK_HOST}",
        "admin",
        "secret",
        "/zm/",
        "/zm/cgi-bin/nph-zms",
        True,
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_without_auth(
    hass: HomeAssistant, mock_zoneminder_client: MagicMock
) -> None:
    """Test the user flow for a server without authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PATH: "/zm/",
        CONF_PATH_ZMS: "/zm/cgi-bin/nph-zms",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }
    mock_zoneminder_client.mock_cls.assert_called_once_with(
        f"http://{MOCK_HOST}", None, None, "/zm/", "/zm/cgi-bin/nph-zms", True
    )


@pytest.mark.parametrize(
    ("side_effect", "return_value", "error"),
    [
        pytest.param(RequestsConnectionError, True, "cannot_connect", id="refused"),
        pytest.param(RequestsTimeout, True, "cannot_connect", id="timeout"),
        pytest.param(None, False, "invalid_auth", id="invalid_auth"),
        pytest.param(RuntimeError, True, "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    side_effect: type[Exception] | None,
    return_value: bool,
    error: str,
) -> None:
    """Test the user flow shows an error and recovers."""
    mock_zoneminder_client.login.side_effect = side_effect
    mock_zoneminder_client.login.return_value = return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_zoneminder_client.login.side_effect = None
    mock_zoneminder_client.login.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("platform_options", "expected_options"),
    [
        pytest.param({}, MOCK_OPTIONS, id="defaults"),
        pytest.param(
            {
                CONF_INCLUDE_ARCHIVED: True,
                CONF_COMMAND_ON: "record",
                CONF_COMMAND_OFF: "none",
            },
            {
                CONF_INCLUDE_ARCHIVED: True,
                CONF_COMMAND_ON: "record",
                CONF_COMMAND_OFF: "none",
            },
            id="platform_options",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_zoneminder_client")
async def test_import_flow(
    hass: HomeAssistant,
    platform_options: dict[str, Any],
    expected_options: dict[str, Any],
) -> None:
    """Test importing a server from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG_DATA, **platform_options},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG_DATA
    assert result["options"] == expected_options


@pytest.mark.parametrize(
    ("side_effect", "return_value", "reason"),
    [
        pytest.param(RequestsConnectionError, True, "cannot_connect", id="refused"),
        pytest.param(None, False, "invalid_auth", id="invalid_auth"),
        pytest.param(RuntimeError, True, "unknown", id="unknown"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    side_effect: type[Exception] | None,
    return_value: bool,
    reason: str,
) -> None:
    """Test the import flow aborts when the server cannot be logged in to."""
    mock_zoneminder_client.login.side_effect = side_effect
    mock_zoneminder_client.login.return_value = return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_options = {
        CONF_INCLUDE_ARCHIVED: True,
        CONF_COMMAND_ON: "mocord",
        CONF_COMMAND_OFF: "nodect",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], new_options
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == new_options
    # The entry is reloaded with the new options
    assert len(mock_setup_entry.mock_calls) == 2
