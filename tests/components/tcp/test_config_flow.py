"""Test the TCP config flow."""

from collections.abc import Generator
import ssl
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tcp.const import CONF_TITLE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PAYLOAD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 4242,
    CONF_PAYLOAD: "status",
    "timeout": 10,
    "buffer_size": 1024,
    "ssl": False,
    "verify_ssl": True,
}

IMPORT_INPUT = {**USER_INPUT, CONF_TITLE: "TCP Sensor"}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Avoid setting up the entry."""
    with patch(
        "homeassistant.components.tcp.async_setup_entry", return_value=None
    ) as mock:
        yield mock


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.1:4242"
    assert result["data"] == USER_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the error is shown and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test a duplicate entry is aborted."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import flow creates an entry."""
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TCP Sensor"
    assert result["data"] == USER_INPUT


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the import flow aborts when the server is unreachable."""
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_duplicate(hass: HomeAssistant) -> None:
    """Test the import flow aborts on duplicates."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguring an entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**USER_INPUT, CONF_PORT: 4343}
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_input


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the error shown when the server is unreachable."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_input = {**USER_INPUT, CONF_PORT: 4343}
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == USER_INPUT
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_input


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test a plain connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.tcp.config_flow.socket.create_connection",
        side_effect=OSError("Boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch("homeassistant.components.tcp.config_flow.socket.create_connection"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_tls_handshake_fails(hass: HomeAssistant) -> None:
    """Test the TLS handshake is validated."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch("homeassistant.components.tcp.config_flow.socket.create_connection"),
        patch(
            "homeassistant.components.tcp.config_flow.ssl.create_default_context"
        ) as mock_context,
    ):
        mock_context.return_value.wrap_socket.side_effect = ssl.SSLError("Boom")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "ssl": True}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_user_flow_tls_success(hass: HomeAssistant, verify_ssl: bool) -> None:
    """Test the handshake uses the configured verification setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch("homeassistant.components.tcp.config_flow.socket.create_connection"),
        patch(
            "homeassistant.components.tcp.config_flow.ssl.create_default_context"
        ) as mock_context,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "ssl": True, "verify_ssl": verify_ssl}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert bool(mock_context.return_value.check_hostname) is verify_ssl


async def test_same_endpoint_different_template(hass: HomeAssistant) -> None:
    """Test entries with different templates are not duplicates."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)
    data = {**USER_INPUT, "value_template": "{{ value.split(';')[1] }}"}

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={**data, CONF_TITLE: "B"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data


async def test_reconfigure_duplicate(hass: HomeAssistant) -> None:
    """Test reconfiguring into another entry's endpoint is aborted."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={**USER_INPUT, CONF_PORT: 4343})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
