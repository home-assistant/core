"""Configuration and authentication flows."""

from unittest.mock import Mock, patch

import grpc
from lorawan_connection import ConnectionUnavailable
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    ("endpoint", "expected_endpoint"),
    [
        ("http://server:8080", "http://server:8080"),
        (
            "http://192.168.1.74:8080/#/tenants/"
            "e434c4e4-534f-4991-9613-c6b90aa871a3/api-keys/create",
            "http://192.168.1.74:8080",
        ),
        ("https://server/devices?limit=10#details", "https://server"),
        ("http://[::1]:8080/#/tenants", "http://[::1]:8080"),
        ("  https://server:8443/  ", "https://server:8443"),
    ],
)
async def test_global_key(
    hass: HomeAssistant,
    mock_connection: Mock,
    endpoint: str,
    expected_endpoint: str,
) -> None:
    """Connect and save the server address from a pasted ChirpStack URL."""
    with patch(
        "homeassistant.components.chirpstack.config_flow.ChirpStackConnection",
        return_value=mock_connection,
    ) as constructor:
        result = await hass.config_entries.flow.async_init(
            "chirpstack",
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"endpoint": endpoint, "api_key": "secret"}
        )
    assert constructor.call_args.args[0] == expected_endpoint
    assert result["step_id"] == "applications"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    assert result["data"]["tenant_id"] == "tenant"
    assert result["data"]["endpoint"] == expected_endpoint
    assert "network_id" not in result["data"]
    mock_connection.inventory.assert_awaited_once()
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    "status", [grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED]
)
async def test_scoped_key(
    hass: HomeAssistant, mock_connection: Mock, status: grpc.StatusCode
) -> None:
    """Scoped keys need a tenant UUID but do not require write access."""
    mock_connection.tenants.side_effect = grpc.aio.AioRpcError(status, (), (), "")
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "readonly"}
    )
    assert result["step_id"] == "tenant"
    mock_connection.close.assert_awaited_once()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tenant_id": "tenant"}
    )
    assert result["step_id"] == "applications"


@pytest.mark.parametrize(
    "status", [grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED]
)
async def test_invalid_auth(
    hass: HomeAssistant, mock_connection: Mock, status: grpc.StatusCode
) -> None:
    """A tenant read disambiguates a scoped key from a rejected credential."""
    mock_connection.tenants.side_effect = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAUTHENTICATED, (), (), "bad key"
    )
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "bad"}
    )
    assert result["step_id"] == "tenant"
    mock_connection.applications.side_effect = grpc.aio.AioRpcError(status, (), (), "")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tenant_id": "tenant"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_connection.tenants.side_effect = None
    mock_connection.applications.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "correct"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


async def test_reauth(
    hass: HomeAssistant, connection_entry: MockConfigEntry, mock_connection: Mock
) -> None:
    """Replace the key while preserving network and device identity."""
    result = await connection_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["reason"] == "reauth_successful"
    assert connection_entry.data["api_key"] == "replacement"
    assert connection_entry.unique_id == "tenant"
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_initial_form(hass: HomeAssistant) -> None:
    """Show connection fields before attempting network access."""
    result = await hass.config_entries.flow.async_init(
        "chirpstack", context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert not result["errors"]


@pytest.mark.parametrize("endpoint", ["ftp://server", "http://[invalid"])
async def test_invalid_endpoint(
    hass: HomeAssistant, mock_connection: Mock, endpoint: str
) -> None:
    """Keep malformed endpoints in the connection form."""
    with patch(
        "homeassistant.components.chirpstack.config_flow.ChirpStackConnection",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_init(
            "chirpstack",
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"endpoint": endpoint, "api_key": "secret"}
        )
    assert result["errors"] == {"base": "invalid_endpoint"}
    mock_connection.tenants.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "correct"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "error",
    [
        ConnectionUnavailable(),
        grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, (), (), "offline"),
    ],
)
async def test_tenant_listing_failure(
    hass: HomeAssistant, mock_connection: Mock, error: Exception
) -> None:
    """Connection and incomplete-list failures remain in the form."""
    mock_connection.tenants.side_effect = error
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    mock_connection.close.assert_awaited_once()

    mock_connection.tenants.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "correct"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


async def test_multiple_tenants(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Offer a tenant selector when a key can access several tenants."""
    mock_connection.tenants.return_value = {"tenant": "Home", "second": "Office"}
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["step_id"] == "tenant"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tenant_id": "second"}
    )
    assert result["step_id"] == "applications"


@pytest.mark.parametrize(
    "error",
    [
        ConnectionUnavailable(),
        grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, (), (), "offline"),
    ],
)
async def test_application_listing_failure(
    hass: HomeAssistant, mock_connection: Mock, error: Exception
) -> None:
    """Keep the chosen tenant when application enumeration fails."""
    mock_connection.applications.side_effect = error
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["step_id"] == "tenant"
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_connection.close.await_count == 2

    mock_connection.applications.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tenant_id": "tenant"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


async def test_no_applications(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Explain that an application must first be created on the server."""
    mock_connection.applications.return_value = {}
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["reason"] == "no_applications"
    mock_connection.inventory.assert_not_awaited()


async def test_empty_selection(hass: HomeAssistant, mock_connection: Mock) -> None:
    """An existing application must be selected before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": []}
    )
    assert result["step_id"] == "applications"
    assert result["errors"] == {"application_ids": "select_application"}
    mock_connection.inventory.assert_not_awaited()
    assert not hass.config_entries.async_entries("chirpstack")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "error",
    [
        ConnectionUnavailable("Application removed"),
        grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, (), (), "offline"),
    ],
)
async def test_inventory_access_failure(
    hass: HomeAssistant, mock_connection: Mock, error: Exception
) -> None:
    """Retry inventory connection failures without losing the application selection."""
    mock_connection.inventory.side_effect = error
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["step_id"] == "applications"
    assert result["errors"] == {"base": "cannot_connect"}
    mock_connection.inventory.assert_awaited_once()
    assert mock_connection.close.await_count == 3
    assert not hass.config_entries.async_entries("chirpstack")

    mock_connection.inventory.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "status", [grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED]
)
async def test_inventory_auth_failure(
    hass: HomeAssistant, mock_connection: Mock, status: grpc.StatusCode
) -> None:
    """A key without inventory access can be replaced in the same flow."""
    mock_connection.inventory.side_effect = grpc.aio.AioRpcError(status, (), (), "")
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "rejected"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_connection.inventory.assert_awaited_once()
    assert mock_connection.close.await_count == 3
    assert not hass.config_entries.async_entries("chirpstack")

    mock_connection.inventory.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "replacement"}
    )
    assert result["step_id"] == "applications"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["api_key"] == "replacement"
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


async def test_reauth_rejected_inventory(
    hass: HomeAssistant, connection_entry: MockConfigEntry, mock_connection: Mock
) -> None:
    """An unusable replacement key never overwrites working entry credentials."""
    mock_connection.inventory.side_effect = ConnectionUnavailable(
        "Selected application missing"
    )
    result = await connection_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert connection_entry.data["api_key"] == "secret"

    mock_connection.inventory.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "replacement"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert connection_entry.data["api_key"] == "replacement"
    await hass.async_block_till_done()


async def test_duplicate_network(hass: HomeAssistant, mock_connection: Mock) -> None:
    """The same endpoint and tenant cannot create another provider entry."""
    entry = MockConfigEntry(domain="chirpstack", unique_id="tenant")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["reason"] == "already_configured"


async def test_reenter_key_after_tenant_auth_failure(
    hass: HomeAssistant, mock_connection: Mock
) -> None:
    """A bad key can be corrected without abandoning the config flow."""
    mock_connection.tenants.side_effect = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAUTHENTICATED, (), (), "Rejected"
    )
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "wrong"}
    )
    assert result["step_id"] == "tenant"
    mock_connection.applications.side_effect = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAUTHENTICATED, (), (), "Rejected"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tenant_id": "tenant"}
    )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_connection.tenants.side_effect = None
    mock_connection.applications.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "correct"}
    )
    assert result["step_id"] == "applications"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("method", "step", "retry_input"),
    [
        ("tenants", "user", {"endpoint": "http://server:8080", "api_key": "secret"}),
        ("applications", "tenant", {"tenant_id": "tenant"}),
    ],
)
async def test_unexpected_error(
    hass: HomeAssistant,
    mock_connection: Mock,
    method: str,
    step: str,
    retry_input: dict[str, str],
) -> None:
    """Unexpected library failures stay in the configuration flow."""
    getattr(mock_connection, method).side_effect = RuntimeError("unexpected")
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    assert result["step_id"] == step
    assert result["errors"] == {"base": "unknown"}

    getattr(mock_connection, method).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], retry_input
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()


async def test_unexpected_validation_error(
    hass: HomeAssistant, mock_connection: Mock
) -> None:
    """Unexpected validation failures preserve the application selection form."""
    mock_connection.inventory.side_effect = RuntimeError("unexpected")
    result = await hass.config_entries.flow.async_init(
        "chirpstack",
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"endpoint": "http://server:8080", "api_key": "secret"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["errors"] == {"base": "unknown"}

    mock_connection.inventory.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"application_ids": ["application"]}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tenant"
    await hass.async_block_till_done()
