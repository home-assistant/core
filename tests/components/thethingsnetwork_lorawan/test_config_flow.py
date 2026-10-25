"""Configuration, discovery, and authentication flows."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import ConnectionUnavailable
from lorawan_connection.backend.tts import AuthenticationError, TTSConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "thethingsnetwork_lorawan"
CREDENTIALS = {
    "endpoint": "https://server:8884",
    "identity_server": "https://identity:8884",
    "api_key": "secret",
}
INPUT = {**CREDENTIALS, "application_ids": ["application"]}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent connection setup after a configuration flow creates its entry."""
    with patch(
        "homeassistant.components.thethingsnetwork_lorawan.async_setup_entry",
        return_value=None,
    ) as setup_entry:
        yield setup_entry


async def test_initial_form(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Show configuration without contacting the network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    assert list(result["data_schema"].schema) == ["region"]
    mock_connection.applications.assert_not_awaited()
    mock_connection.async_connect.assert_not_awaited()


@pytest.mark.parametrize("region", ["eu1", "nam1", "au1"])
async def test_region(hass: HomeAssistant, mock_connection: Mock, region: str) -> None:
    """Discover applications through EU1 before connecting to regional traffic."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": region}
    )
    assert list(result["data_schema"].schema) == ["api_key"]
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        return_value=mock_connection,
    ) as constructor:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "secret"}
        )
        assert result["step_id"] == "applications"
        constructor.assert_called_once_with(
            f"https://{region}.cloud.thethings.network:8884",
            "secret",
            identity_server="https://eu1.cloud.thethings.network:8884",
            application_ids=[],
            network_id="validation",
        )
        mock_connection.applications.assert_awaited_once_with()
        mock_connection.async_connect.assert_not_awaited()
        selector = next(iter(result["data_schema"].schema.values()))
        assert selector.config["options"] == [
            {"value": "application", "label": "Application"},
            {"value": "second", "label": "Second"},
        ]
        assert selector.config["multiple"] is True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"application_ids": ["application"]}
        )
        constructor.assert_called_with(
            f"https://{region}.cloud.thethings.network:8884",
            "secret",
            identity_server="https://eu1.cloud.thethings.network:8884",
            application_ids=["application"],
            network_id="validation",
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["result"].unique_id
        == "https://eu1.cloud.thethings.network:8884:application"
    )
    assert result["data"] == {
        "endpoint": f"https://{region}.cloud.thethings.network:8884",
        "identity_server": "https://eu1.cloud.thethings.network:8884",
        "api_key": "secret",
        "application_ids": ["application"],
    }
    mock_connection.async_connect.assert_awaited_once_with()
    assert mock_connection.close.await_count == 2
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("endpoint", "identity_server", "expected_endpoint", "expected_identity"),
    [
        (
            "https://server:8884",
            "https://identity:8884",
            "https://server:8884",
            "https://identity:8884",
        ),
        (
            "https://server:8884/console/applications/app?view=1#devices",
            "https://identity:8884/console",
            "https://server:8884",
            "https://identity:8884",
        ),
        ("  http://[::1]:1884/  ", " ", "http://[::1]:1884", "http://[::1]:1884"),
        (
            "https://SERVER:8884/console?view=1#devices",
            "https://IDENTITY:8884/console",
            "https://server:8884",
            "https://identity:8884",
        ),
        (
            "http://[FE80::1%25ETH0]:1884/console",
            "",
            "http://[fe80::1%25ETH0]:1884",
            "http://[fe80::1%25ETH0]:1884",
        ),
    ],
)
async def test_custom_server(
    hass: HomeAssistant,
    mock_connection: Mock,
    endpoint: str,
    identity_server: str,
    expected_endpoint: str,
    expected_identity: str,
) -> None:
    """Normalize pasted URLs before fetching the application list."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    assert list(result["data_schema"].schema) == [
        "endpoint",
        "identity_server",
        "api_key",
    ]
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        return_value=mock_connection,
    ) as constructor:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**CREDENTIALS, "endpoint": endpoint, "identity_server": identity_server},
        )
        constructor.assert_called_once_with(
            expected_endpoint,
            "secret",
            identity_server=expected_identity,
            application_ids=[],
            network_id="validation",
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"application_ids": ["second", "application"]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "application, second"
    assert result["result"].unique_id == f"{expected_identity}:application,second"
    assert result["data"] == {
        "endpoint": expected_endpoint,
        "identity_server": expected_identity,
        "api_key": "secret",
        "application_ids": ["application", "second"],
    }
    await hass.async_block_till_done()


async def test_no_applications(hass: HomeAssistant, mock_connection: Mock) -> None:
    """An authenticated key with no applications cannot create an entry."""
    mock_connection.applications.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "eu1"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_applications"
    mock_connection.close.assert_awaited_once_with()
    mock_connection.async_connect.assert_not_awaited()


async def test_empty_selection(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Require a selection before opening traffic subscriptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": []}
    )
    assert result["errors"] == {"application_ids": "select_application"}
    mock_connection.async_connect.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("region", "credentials", "identity"),
    [
        ("nam1", {"api_key": "secret"}, "https://eu1.cloud.thethings.network:8884"),
        ("custom", CREDENTIALS, "https://identity:8884"),
    ],
)
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), "invalid_auth"),
        (ConnectionUnavailable(), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_discovery_error(
    hass: HomeAssistant,
    mock_connection: Mock,
    region: str,
    credentials: dict[str, str],
    identity: str,
    error: Exception,
    expected: str,
) -> None:
    """Failed authentication or listing allows the user to replace credentials."""
    mock_connection.applications.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": region}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], credentials
    )
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": expected}
    mock_connection.close.assert_awaited_once_with()
    mock_connection.async_connect.assert_not_awaited()
    mock_connection.applications.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**credentials, "api_key": "replacement"}
    )
    assert result["step_id"] == "applications"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{identity}:application"
    assert result["data"]["api_key"] == "replacement"
    await hass.async_block_till_done()


@pytest.mark.parametrize("field", ["endpoint", "identity_server"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://server",
        "http://[invalid",
        "https://server:bad",
        "https://user:pass@server",
    ],
)
async def test_invalid_endpoint(
    hass: HomeAssistant, mock_connection: Mock, field: str, endpoint: str
) -> None:
    """Invalid addresses never start discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        side_effect=TTSConnection,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CREDENTIALS, field: endpoint}
        )
    assert result["errors"] == {"base": "invalid_endpoint"}
    mock_connection.applications.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["step_id"] == "applications"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConnectionUnavailable(), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_connection_error(
    hass: HomeAssistant, mock_connection: Mock, error: Exception, expected: str
) -> None:
    """Device and traffic access are checked after application selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    mock_connection.async_connect.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["step_id"] == "applications"
    assert result["errors"] == {"base": expected}
    assert mock_connection.close.await_count == 2
    mock_connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


async def test_missing_application_rights(
    hass: HomeAssistant, mock_connection: Mock
) -> None:
    """Return to credentials when the key cannot read selected devices or traffic."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    mock_connection.async_connect.side_effect = AuthenticationError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CREDENTIALS, "api_key": "replacement"}
    )
    assert result["step_id"] == "applications"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["second"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:second"
    assert result["data"]["application_ids"] == ["second"]
    await hass.async_block_till_done()


async def test_cancelled_discovery(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Cancellation closes discovery connections."""
    mock_connection.applications.side_effect = asyncio.CancelledError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    with pytest.raises(asyncio.CancelledError):
        await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    mock_connection.close.assert_awaited_once_with()


@pytest.mark.parametrize("applications", [["application"], ["application", "second"]])
@pytest.mark.parametrize(
    ("stored_identity", "identity"),
    [
        ("https://identity:8884", "https://identity:8884"),
        ("https://identity:8884", "https://IDENTITY:8884"),
        ("https://IDENTITY:8884", "https://identity:8884"),
        ("https://identity:443", "https://IDENTITY"),
    ],
)
async def test_duplicate_application(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    applications: list[str],
    stored_identity: str,
    identity: str,
) -> None:
    """Reject overlapping applications after normalizing server URLs."""
    hass.config_entries.async_update_entry(
        connection_entry,
        data={**connection_entry.data, "identity_server": stored_identity},
        unique_id=f"{stored_identity}:application",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CREDENTIALS, "identity_server": identity}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": applications}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("identity", "applications", "unique_id"),
    [
        ("https://identity:8884", ["second"], "https://identity:8884:second"),
        ("https://another:8884", ["application"], "https://another:8884:application"),
    ],
)
async def test_distinct_application(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    identity: str,
    applications: list[str],
    unique_id: str,
) -> None:
    """Other applications and deployments can be configured independently."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CREDENTIALS, "identity_server": identity}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": applications}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == unique_id
    await hass.async_block_till_done()


async def test_reauth(
    hass: HomeAssistant, connection_entry: MockConfigEntry, mock_connection: Mock
) -> None:
    """Replace credentials without changing the application or connection identity."""
    result = await connection_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["reason"] == "reauth_successful"
    assert connection_entry.data == {**INPUT, "api_key": "replacement"}
    assert connection_entry.unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), "invalid_auth"),
        (ConnectionUnavailable(), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_reauth_error(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
    error: Exception,
    expected: str,
) -> None:
    """An invalid replacement does not overwrite stored credentials."""
    mock_connection.async_connect.side_effect = error
    result = await connection_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["errors"] == {"base": expected}
    assert connection_entry.data == INPUT
    mock_connection.close.assert_awaited_once_with()
    mock_connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
