"""Test Onkyo config flow."""
import asyncio

from homeassistant import config_entries, core
from homeassistant.components.onkyo.const import (
    CONF_ENABLED_SOURCES,
    CONF_IDENTIFIER,
    CONF_MAX_VOLUME,
    CONF_SOURCES,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import AsyncMock, Mock, MockConfigEntry, patch

TEST_NAME_1 = "OnkyoReceiver"
TEST_NAME_2 = "PioneerReceiver"
TEST_HOST_1 = "192.168.1.2"
TEST_HOST_2 = "192.168.1.3"
TEST_IDENTIFIER_1 = "0123456789"
TEST_IDENTIFIER_2 = "9876543210"

TEST_MAX_VOLUME = 200
TEST_ENABLED_SOURCES = ["tv", "dvd"]
TEST_CUSTOM_SOURCE_NAMES = {
    "tv": "CustomNameTV",
    "dvd": "CustomNameDVD",
}


def get_mock_connection(host, name, identifier):
    """Return a mock connection."""
    mock_connection = Mock()
    mock_connection.name = name
    mock_connection.host = host
    mock_connection.identifier = identifier

    mock_connection.connect = AsyncMock()
    mock_connection.close = Mock()

    return mock_connection


async def test_config_flow_import_invalid_host(hass: core.HomeAssistant):
    """Test if an import flow aborts if no connection is discovered."""
    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: TEST_HOST_1,
                CONF_NAME: TEST_NAME_1,
                CONF_MAX_VOLUME: TEST_MAX_VOLUME,
                CONF_SOURCES: TEST_CUSTOM_SOURCE_NAMES,
            },
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_config_flow_import_success(hass: core.HomeAssistant):
    """Test if an import flow succeeds when discovering a connection."""
    mock_connection = get_mock_connection(TEST_HOST_1, TEST_NAME_1, TEST_IDENTIFIER_1)

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[mock_connection],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: TEST_HOST_1,
                CONF_NAME: TEST_NAME_1,
                CONF_MAX_VOLUME: TEST_MAX_VOLUME,
                CONF_SOURCES: TEST_CUSTOM_SOURCE_NAMES,
            },
        )

    assert len(mock_connection.connect.mock_calls) == 1
    assert len(mock_connection.close.mock_calls) == 1

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_NAME_1
    assert result["data"] == {
        CONF_IDENTIFIER: TEST_IDENTIFIER_1,
        CONF_HOST: TEST_HOST_1,
        CONF_NAME: TEST_NAME_1,
    }
    assert result["options"] == {
        CONF_MAX_VOLUME: TEST_MAX_VOLUME,
        CONF_SOURCES: TEST_CUSTOM_SOURCE_NAMES,
    }


async def test_config_flow_manual_not_discovered(hass):
    """Test if a manual flow returns a discovery error when no connection is discovered."""

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST_1},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "discovery_error"}


async def test_config_flow_manual_discovered(hass):
    """Test if a manual flow succeeds when a connection is discovered."""
    mock_connection = get_mock_connection(TEST_HOST_1, TEST_NAME_1, TEST_IDENTIFIER_1)

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[mock_connection],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST_1},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_NAME_1
    assert result["data"] == {
        CONF_IDENTIFIER: TEST_IDENTIFIER_1,
        CONF_HOST: TEST_HOST_1,
        CONF_NAME: TEST_NAME_1,
    }


async def test_config_flow_manual_single_avr_cannot_connect(hass: core.HomeAssistant):
    """Test if a manual flow aborts if the connection cannot connect."""
    mock_connection = get_mock_connection(TEST_HOST_1, TEST_NAME_1, TEST_IDENTIFIER_1)

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[mock_connection],
    ):
        mock_connection.connect.side_effect = asyncio.TimeoutError()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert len(mock_connection.connect.mock_calls) == 1

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_config_flow_manual_single_avr_success(hass: core.HomeAssistant):
    """Test if a manual flow succeeds when discovering a single connection."""
    mock_connection = get_mock_connection(TEST_HOST_1, TEST_NAME_1, TEST_IDENTIFIER_1)

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[mock_connection],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert len(mock_connection.connect.mock_calls) == 1
    assert len(mock_connection.close.mock_calls) == 1

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_NAME_1
    assert result["data"] == {
        CONF_IDENTIFIER: TEST_IDENTIFIER_1,
        CONF_HOST: TEST_HOST_1,
        CONF_NAME: TEST_NAME_1,
    }


async def test_config_flow_manual_dual_avrs_success(hass: core.HomeAssistant):
    """Test if a manual flow succeeds when discovering two connections."""
    mock_connection_1 = get_mock_connection(TEST_HOST_1, TEST_NAME_1, TEST_IDENTIFIER_1)
    mock_connection_2 = get_mock_connection(TEST_HOST_2, TEST_NAME_2, TEST_IDENTIFIER_2)

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover_connections",
        return_value=[mock_connection_1, mock_connection_2],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "select"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_receiver": TEST_NAME_2},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_NAME_2
    assert result["data"] == {
        CONF_IDENTIFIER: TEST_IDENTIFIER_2,
        CONF_HOST: TEST_HOST_2,
        CONF_NAME: TEST_NAME_2,
    }


async def test_options_flow(hass: core.HomeAssistant):
    """Test options config flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_IDENTIFIER_1,
        data={
            CONF_IDENTIFIER: TEST_IDENTIFIER_1,
            CONF_HOST: TEST_HOST_1,
            CONF_NAME: TEST_NAME_1,
        },
        title=TEST_NAME_1,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAX_VOLUME: TEST_MAX_VOLUME,
            CONF_ENABLED_SOURCES: TEST_ENABLED_SOURCES,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "source_names"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=TEST_CUSTOM_SOURCE_NAMES,
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_MAX_VOLUME: TEST_MAX_VOLUME,
        CONF_SOURCES: TEST_CUSTOM_SOURCE_NAMES,
    }
