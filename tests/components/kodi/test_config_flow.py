"""Test the Kodi config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import ANY, AsyncMock, PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.kodi.config_flow import (
    CannotConnectError,
    InvalidAuthError,
)
from homeassistant.components.kodi.const import CONF_WS_PORT, DEFAULT_TIMEOUT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import (
    TEST_CREDENTIALS,
    TEST_DISCOVERY,
    TEST_DISCOVERY_WO_UUID,
    TEST_HOST,
    TEST_WS_PORT,
    UUID,
    MockConnection,
    MockWSConnection,
    get_kodi_connection,
)

from tests.common import MockConfigEntry


@contextmanager
def _patch_kodi_success() -> Generator[None]:
    """Patch a reachable Kodi and the entry setup."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
        patch(
            "homeassistant.components.kodi.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture
async def user_flow(hass: HomeAssistant) -> str:
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    return result["flow_id"]


async def test_user_flow(hass: HomeAssistant, user_flow: str) -> None:
    """Test a successful user initiated flow."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
        patch(
            "homeassistant.components.kodi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)
        await hass.async_block_till_done()

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST["host"]
    assert result["data"] == {
        **TEST_HOST,
        **TEST_WS_PORT,
        "password": None,
        "username": None,
        "name": None,
        "timeout": DEFAULT_TIMEOUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_valid_auth(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle valid auth."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=InvalidAuthError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
        patch(
            "homeassistant.components.kodi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CREDENTIALS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST["host"]
    assert result["data"] == {
        **TEST_HOST,
        **TEST_WS_PORT,
        **TEST_CREDENTIALS,
        "name": None,
        "timeout": DEFAULT_TIMEOUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_valid_ws_port(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle valid websocket port."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
        patch(
            "homeassistant.components.kodi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST["host"]
    assert result["data"] == {
        **TEST_HOST,
        **TEST_WS_PORT,
        "password": None,
        "username": None,
        "name": None,
        "timeout": DEFAULT_TIMEOUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_empty_ws_port(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle an empty websocket port input."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.kodi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ws_port": 0}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST["host"]
    assert result["data"] == {
        **TEST_HOST,
        "ws_port": None,
        "password": None,
        "username": None,
        "name": None,
        "timeout": DEFAULT_TIMEOUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle invalid auth."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=InvalidAuthError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=InvalidAuthError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=CannotConnectError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect_http(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle cannot connect over HTTP error."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=CannotConnectError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_HOST
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_exception_http(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle generic exception over HTTP."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_HOST
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect_ws(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle cannot connect over WebSocket error."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection, "connected", new_callable=PropertyMock(return_value=False)
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=CannotConnectError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {"base": "cannot_connect"}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_exception_ws(hass: HomeAssistant, user_flow: str) -> None:
    """Test we handle generic exception over WebSocket."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(MockWSConnection, "connect", AsyncMock(side_effect=Exception)),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {"base": "unknown"}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_discovery(hass: HomeAssistant) -> None:
    """Test discovery flow works."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(
        "homeassistant.components.kodi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "hostname"
    assert result["data"] == {
        **TEST_HOST,
        **TEST_WS_PORT,
        "password": None,
        "username": None,
        "name": "hostname",
        "timeout": DEFAULT_TIMEOUT,
    }
    assert result["result"].unique_id == UUID

    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_cannot_connect_http(hass: HomeAssistant) -> None:
    """Test discovery aborts if cannot connect."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=CannotConnectError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovery_cannot_connect_ws(hass: HomeAssistant) -> None:
    """Test discovery aborts if cannot connect to websocket."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch.object(
            MockWSConnection,
            "connect",
            AsyncMock(side_effect=CannotConnectError),
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            new=get_kodi_connection,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ws_port"
    assert result["errors"] == {}


async def test_discovery_exception_http(hass: HomeAssistant) -> None:
    """Test we handle generic exception during discovery validation."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_discovery_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth during discovery."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=InvalidAuthError,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {}


async def test_discovery_duplicate_data(hass: HomeAssistant) -> None:
    """Test discovery aborts if same mDNS packet arrives."""
    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            return_value=True,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=TEST_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass: HomeAssistant) -> None:
    """Test a duplicate discovery id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UUID,
        data={"host": "dummy", "port": 11, "namename": "dummy.local."},
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["port"] == 8080
    assert entry.data["name"] == "hostname"


async def test_discovery_without_unique_id(hass: HomeAssistant) -> None:
    """Test a discovery flow with no unique id aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=TEST_DISCOVERY_WO_UUID,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_uuid"


REAUTH_ENTRY_DATA = {
    CONF_NAME: "name",
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 8080,
    CONF_WS_PORT: 9090,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "old_password",
    CONF_SSL: False,
}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the credentials."""
    entry = MockConfigEntry(domain=DOMAIN, data=REAUTH_ENTRY_DATA, unique_id=UUID)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        _patch_kodi_success(),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ) as mock_get_connection,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new_user", CONF_PASSWORD: "new_password"},
        )
        await hass.async_block_till_done()

    mock_get_connection.assert_called_once_with(
        "1.1.1.1", 8080, None, "new_user", "new_password", False, session=ANY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == REAUTH_ENTRY_DATA | {
        CONF_USERNAME: "new_user",
        CONF_PASSWORD: "new_password",
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(InvalidAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(CannotConnectError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(domain=DOMAIN, data=REAUTH_ENTRY_DATA, unique_id=UUID)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch(
            "homeassistant.components.kodi.config_flow.Kodi.ping",
            side_effect=side_effect,
        ),
        patch(
            "homeassistant.components.kodi.config_flow.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new_user", CONF_PASSWORD: "wrong_password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with _patch_kodi_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new_user", CONF_PASSWORD: "new_password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"
