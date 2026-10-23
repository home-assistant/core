"""Tests for the NX584 config flow."""

from collections.abc import Awaitable, Callable
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
import requests

from homeassistant.components.nx584.const import (
    CONF_ENTITY_NAMESPACES,
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigFlowResult
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
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry

IMPORT_DATA = {
    CONF_PLATFORM: Platform.ALARM_CONTROL_PANEL,
    CONF_HOST: TEST_HOST,
    CONF_PORT: TEST_PORT,
    CONF_NAME: "House",
    CONF_EXCLUDE_ZONES: [2],
    CONF_ZONE_TYPES: {3: "motion"},
}
IMPORTED_DATA = {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT, CONF_NAME: "House"}
IMPORTED_OPTIONS = {CONF_EXCLUDE_ZONES: [2], CONF_ZONE_TYPES: {"3": "motion"}}


@pytest.fixture
def held_validation(
    mock_client: MagicMock, fake_zones: list[dict[str, object]]
) -> tuple[threading.Event, threading.Event]:
    """Hold the first server validation until released."""
    entered = threading.Event()
    release = threading.Event()

    def list_zones() -> list[dict[str, object]]:
        if not entered.is_set():
            entered.set()
            release.wait(5)
        return fake_zones

    # A plain function, as the test executor runs mocks inline in the event loop.
    mock_client.return_value.list_zones = list_zones
    return entered, release


async def _async_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Run the user flow for the test server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )


async def _async_import_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Run the import flow for the test server."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )


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
async def test_user_flow_same_host_other_port(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow sets up another server on the same host."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT + 1}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT + 1}


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


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("first_flow", "second_flow", "data", "options"),
    [
        pytest.param(
            _async_user_flow,
            _async_user_flow,
            {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
            {},
            id="user_then_user",
        ),
        pytest.param(
            _async_import_flow,
            _async_user_flow,
            IMPORTED_DATA,
            IMPORTED_OPTIONS,
            id="import_then_user",
        ),
        pytest.param(
            _async_user_flow,
            _async_import_flow,
            IMPORTED_DATA,
            IMPORTED_OPTIONS,
            id="user_then_import",
        ),
    ],
)
async def test_flow_server_configured_during_validation(
    hass: HomeAssistant,
    held_validation: tuple[threading.Event, threading.Event],
    first_flow: Callable[[HomeAssistant], Awaitable[ConfigFlowResult]],
    second_flow: Callable[[HomeAssistant], Awaitable[ConfigFlowResult]],
    data: dict[str, object],
    options: dict[str, object],
) -> None:
    """Test a server set up while a flow validates it is not set up twice."""
    # Loaded first, as loading it waits for the held import flow to finish.
    assert await async_setup_component(hass, DOMAIN, {})
    entered, release = held_validation
    first = hass.async_create_task(first_flow(hass))
    await hass.async_add_executor_job(entered.wait, 5)

    # The second flow sets up the server while the first one still validates it.
    result = await second_flow(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    release.set()
    result = await first
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == data
    assert entries[0].options == options
