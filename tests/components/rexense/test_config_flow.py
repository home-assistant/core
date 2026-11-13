"""Test the complete manual configuration flow."""

from unittest.mock import MagicMock, patch

from aiorexense import (
    RexenseAuthenticationError,
    RexenseConnectionError,
    RexenseError,
    UnsupportedTaxonomyError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.rexense.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONNECTION, GATEWAY_ID

pytestmark = pytest.mark.usefixtures("mock_gateway")


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param(CONNECTION, id="without-auth"),
        pytest.param(
            {
                **CONNECTION,
                CONF_HOST: "gateway.example.com",
                CONF_PORT: 8443,
                CONF_API_KEY: "example-key",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
            },
            id="authenticated-tls",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_client: MagicMock, settings: dict[str, object]
) -> None:
    """Create a unique entry and close the configuration socket."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=settings
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rexense RG5100"
    assert result["data"] == settings
    assert result["result"].unique_id == GATEWAY_ID
    mock_client.async_connect.assert_awaited_once()
    mock_client.async_close.assert_awaited_once()


async def test_default_connection_fields(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Only a host is required when gateway authentication is disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: CONNECTION[CONF_HOST]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CONNECTION
    assert result["result"].unique_id == GATEWAY_ID
    mock_client.async_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(RexenseAuthenticationError, "invalid_auth", id="authentication"),
        pytest.param(UnsupportedTaxonomyError, "unsupported_gateway", id="taxonomy"),
        pytest.param(RexenseConnectionError, "cannot_connect", id="connection"),
        pytest.param(RexenseError, "cannot_connect", id="protocol"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(ValueError, "cannot_connect", id="invalid-host"),
        pytest.param(RuntimeError, "unknown", id="unexpected"),
    ],
)
async def test_error_and_recovery(
    hass: HomeAssistant,
    mock_client: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Recover within the same flow after every connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_client.async_connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONNECTION
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_client.async_close.assert_awaited_once()

    mock_client.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONNECTION
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == GATEWAY_ID
    assert mock_client.async_close.await_count == 2


async def test_duplicate_gateway(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reject a gateway already configured at another IP address."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**CONNECTION, CONF_HOST: "192.0.2.2"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_client.async_close.assert_awaited_once()


@pytest.mark.usefixtures("mock_client")
async def test_invalid_host_recovers(hass: HomeAssistant) -> None:
    """Reject an invalid constructor input without creating a socket."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.rexense.config_flow.RexenseClient",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONNECTION
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONNECTION
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == GATEWAY_ID


async def test_gateway_without_model(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Use the manufacturer name if the gateway omits an optional model."""
    del mock_client.async_connect.return_value["system"]["model"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONNECTION
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rexense gateway"
    assert result["result"].unique_id == GATEWAY_ID


async def test_gateway_identity_from_network(
    hass: HomeAssistant, mock_client: MagicMock, mock_gateway: MagicMock
) -> None:
    """Keep the library's stable network identity when system metadata is absent."""
    info = {
        "code": 0,
        "taxonomy_version": 3,
        "network": {"eth": {"mac": "00:11:22:33:44:55"}},
    }
    mock_client.async_connect.return_value = info
    mock_gateway.gateway = info
    mock_gateway.unique_id = "001122334455"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONNECTION
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rexense gateway"
    assert result["result"].unique_id == "001122334455"
