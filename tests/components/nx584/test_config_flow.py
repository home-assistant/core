"""Tests for the NX584 config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import requests

from homeassistant.components.nx584.const import (
    CONF_ENTITY_NAMESPACES,
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NX584"
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    assert result["result"].unique_id == f"{TEST_HOST}:{TEST_PORT}"
    mock_client.assert_called_with(f"http://{TEST_HOST}:{TEST_PORT}")


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            requests.exceptions.ConnectionError, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(requests.exceptions.Timeout, "cannot_connect", id="timeout"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the user flow shows an error and recovers."""
    mock_client.return_value.list_zones.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.return_value.list_zones.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts for a server that is already set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import keeps the zone settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_PLATFORM: Platform.BINARY_SENSOR,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_EXCLUDE_ZONES: [2],
            CONF_ZONE_TYPES: {3: "motion"},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NX584"
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    assert result["options"] == {
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {"3": "motion"},
    }
    assert result["result"].unique_id == f"{TEST_HOST}:{TEST_PORT}"


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_import_flow_merges_into_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an import for a server set up from the UI keeps all platforms."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_PLATFORM: Platform.BINARY_SENSOR,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_EXCLUDE_ZONES: [1],
            CONF_ZONE_TYPES: {},
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    assert mock_config_entry.options == {
        CONF_EXCLUDE_ZONES: [1],
        CONF_ZONE_TYPES: {},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_PLATFORM: Platform.ALARM_CONTROL_PANEL,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_NAME: "House",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_NAME: "House",
    }
    assert mock_config_entry.options == {
        CONF_EXCLUDE_ZONES: [1],
        CONF_ZONE_TYPES: {},
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_import_flow_entity_namespaces(hass: HomeAssistant) -> None:
    """Test each import updates only its own platform's entity namespace."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_ENTITY_NAMESPACES: {
                Platform.ALARM_CONTROL_PANEL: "security",
                Platform.BINARY_SENSOR: "zones",
            },
        },
        unique_id=f"{TEST_HOST}:{TEST_PORT}",
    )
    entry.add_to_hass(hass)

    async def _async_import(platform: Platform, namespace: dict[str, str]) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_PLATFORM: platform,
                CONF_HOST: TEST_HOST,
                CONF_PORT: TEST_PORT,
                **namespace,
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    await _async_import(Platform.BINARY_SENSOR, {CONF_ENTITY_NAMESPACE: "sensors"})
    assert entry.data[CONF_ENTITY_NAMESPACES] == {
        Platform.ALARM_CONTROL_PANEL: "security",
        Platform.BINARY_SENSOR: "sensors",
    }

    # A namespace removed from the YAML is removed from the entry.
    await _async_import(Platform.ALARM_CONTROL_PANEL, {})
    assert entry.data[CONF_ENTITY_NAMESPACES] == {Platform.BINARY_SENSOR: "sensors"}

    await _async_import(Platform.BINARY_SENSOR, {})
    assert CONF_ENTITY_NAMESPACES not in entry.data


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(
            requests.exceptions.ConnectionError, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(requests.exceptions.Timeout, "cannot_connect", id="timeout"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the import aborts when the server cannot be validated."""
    mock_client.return_value.list_zones.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_PLATFORM: Platform.ALARM_CONTROL_PANEL,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_NAME: "NX584",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not mock_setup_entry.called
