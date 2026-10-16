"""Configuration, discovery, and authentication flows."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import ConnectionUnavailable
from lorawan_connection.backend.tts import AuthenticationError, TTSConnection
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DOMAIN = "thethingsnetwork_lorawan"
INPUT = {
    "endpoint": "https://server:8884",
    "identity_server": "https://identity:8884",
    "api_key": "secret",
    "application_ids": ["application"],
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent connection setup after a configuration flow creates its entry."""
    with patch(
        "homeassistant.components.thethingsnetwork_lorawan.async_setup_entry",
        return_value=True,
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
    mock_connection.async_connect.assert_not_awaited()


@pytest.mark.parametrize(
    ("region", "endpoint"),
    [
        ("eu1", "https://eu1.cloud.thethings.network:8884"),
        ("nam1", "https://nam1.cloud.thethings.network:8884"),
        ("au1", "https://au1.cloud.thethings.network:8884"),
    ],
)
async def test_region(
    hass: HomeAssistant, mock_connection: Mock, region: str, endpoint: str
) -> None:
    """Regional traffic uses the selected cluster and the central Identity Server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": region}
    )
    assert result["step_id"] == "connection"
    assert list(result["data_schema"].schema) == ["api_key", "application_ids"]
    mock_connection.async_connect.assert_not_awaited()
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        return_value=mock_connection,
    ) as constructor:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "secret", "application_ids": ["application"]},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == (
        "https://eu1.cloud.thethings.network:8884:application"
    )
    assert result["data"] == {
        "endpoint": endpoint,
        "identity_server": "https://eu1.cloud.thethings.network:8884",
        "api_key": "secret",
        "application_ids": ["application"],
    }
    constructor.assert_called_once_with(
        endpoint,
        "secret",
        identity_server="https://eu1.cloud.thethings.network:8884",
        application_ids=["application"],
        network_id="validation",
    )
    mock_connection.async_connect.assert_awaited_once()
    mock_connection.close.assert_awaited_once()
    await hass.async_block_till_done()


async def test_region_retry(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Retain selected server addresses when retrying rejected credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "nam1"}
    )
    mock_connection.async_connect.side_effect = AuthenticationError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "invalid", "application_ids": ["application"]},
    )
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": "invalid_auth"}
    assert list(result["data_schema"].schema) == ["api_key", "application_ids"]
    mock_connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "replacement", "application_ids": ["application"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == (
        "https://eu1.cloud.thethings.network:8884:application"
    )
    assert result["data"] == {
        "endpoint": "https://nam1.cloud.thethings.network:8884",
        "identity_server": "https://eu1.cloud.thethings.network:8884",
        "api_key": "replacement",
        "application_ids": ["application"],
    }
    await hass.async_block_till_done()


async def test_region_duplicate(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """A region preset cannot duplicate an application configured with URLs."""
    hass.config_entries.async_update_entry(
        connection_entry,
        data={
            **connection_entry.data,
            "endpoint": "https://nam1.cloud.thethings.network:8884",
            "identity_server": "https://eu1.cloud.thethings.network:8884",
        },
        unique_id="https://eu1.cloud.thethings.network:8884:application",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "nam1"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "secret", "application_ids": ["application"]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
async def test_user(
    hass: HomeAssistant,
    mock_connection: Mock,
    endpoint: str,
    identity_server: str,
    expected_endpoint: str,
    expected_identity: str,
) -> None:
    """Normalize pasted URLs and application IDs, then check both servers."""
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        return_value=mock_connection,
    ) as constructor:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"region": "custom"}
        )
        assert result["step_id"] == "connection"
        assert list(result["data_schema"].schema) == [
            "endpoint",
            "identity_server",
            "api_key",
            "application_ids",
        ]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **INPUT,
                "endpoint": endpoint,
                "identity_server": identity_server,
                "application_ids": [" second ", "application", "second"],
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "application, second"
    assert result["data"] == {
        **INPUT,
        "endpoint": expected_endpoint,
        "identity_server": expected_identity,
        "application_ids": ["application", "second"],
    }
    assert result["result"].unique_id == f"{expected_identity}:application,second"
    constructor.assert_called_once_with(
        expected_endpoint,
        "secret",
        identity_server=expected_identity,
        application_ids=["application", "second"],
        network_id="validation",
    )
    mock_connection.async_connect.assert_awaited_once_with()
    mock_connection.close.assert_awaited_once_with()
    await hass.async_block_till_done()


async def test_same_server(hass: HomeAssistant, mock_connection: Mock) -> None:
    """The Identity Server defaults to the Application Server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "endpoint": INPUT["endpoint"],
            "api_key": "secret",
            "application_ids": ["application"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://server:8884:application"
    assert result["data"]["identity_server"] == INPUT["endpoint"]
    await hass.async_block_till_done()


@pytest.mark.parametrize("applications", [[], ["", "  "]])
async def test_empty_applications(
    hass: HomeAssistant, mock_connection: Mock, applications: list[str]
) -> None:
    """At least one application is required before connecting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**INPUT, "application_ids": applications}
    )
    assert result["errors"] == {"application_ids": "select_application"}
    mock_connection.async_connect.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
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
    """Invalid addresses never start a connection."""
    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.TTSConnection",
        side_effect=TTSConnection,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"region": "custom"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**INPUT, field: endpoint}
        )
    assert result["errors"] == {"base": "invalid_endpoint"}
    mock_connection.async_connect.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), "invalid_auth"),
        (ConnectionUnavailable(), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_connection_error(
    hass: HomeAssistant, mock_connection: Mock, error: Exception, expected: str
) -> None:
    """Failed validation closes the transport and allows retrying the form."""
    mock_connection.async_connect.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": expected}
    mock_connection.close.assert_awaited_once_with()
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "https://identity:8884:application"
    await hass.async_block_till_done()


async def test_cancelled_validation(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Cancellation still closes the temporary connection."""
    mock_connection.async_connect.side_effect = asyncio.CancelledError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    with pytest.raises(asyncio.CancelledError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], INPUT
        )
    mock_connection.close.assert_awaited_once_with()


@pytest.mark.parametrize("applications", [["application"], ["application", "second"]])
@pytest.mark.parametrize(
    ("stored_identity_server", "identity_server"),
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
    stored_identity_server: str,
    identity_server: str,
) -> None:
    """Overlapping applications cannot register duplicate devices."""
    hass.config_entries.async_update_entry(
        connection_entry,
        data={**connection_entry.data, "identity_server": stored_identity_server},
        unique_id=f"{stored_identity_server}:application",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**INPUT, "application_ids": applications, "identity_server": identity_server},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("changes", "unique_id"),
    [
        ({"application_ids": ["second"]}, "https://identity:8884:second"),
        (
            {"identity_server": "https://another:8884"},
            "https://another:8884:application",
        ),
    ],
)
async def test_distinct_application(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    changes: dict[str, str | list[str]],
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
        result["flow_id"], {**INPUT, **changes}
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
