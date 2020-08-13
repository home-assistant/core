"""Test the Kodi config flow."""
import pytest

from homeassistant import config_entries
from homeassistant.components.kodi.config_flow import (
    CannotConnectError,
    InvalidAuthError,
)
from homeassistant.components.kodi.const import DEFAULT_TIMEOUT, DOMAIN

from .util import (
    TEST_CREDENTIALS,
    TEST_DISCOVERY,
    TEST_HOST,
    TEST_IMPORT,
    TEST_WS_PORT,
    UUID,
    MockConnection,
)

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry


@pytest.fixture
async def user_flow(hass):
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_HOST
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.fixture
async def discovery_flow(hass):
    """Return a discovery flow after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "form"
    assert result["errors"] == {}
    return result["flow_id"]


async def test_user_flow(hass, user_flow):
    """Test a successful user initiated flow."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", return_value=True,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ), patch(
        "homeassistant.components.kodi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kodi.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

        assert result["type"] == "form"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_HOST["host"]
    assert result2["data"] == {
        **TEST_HOST,
        **TEST_CREDENTIALS,
        **TEST_WS_PORT,
        "name": None,
        "timeout": DEFAULT_TIMEOUT,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass, user_flow):
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping",
        side_effect=InvalidAuthError,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect_http(hass, user_flow):
    """Test we handle cannot connect over HTTP error."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping",
        side_effect=CannotConnectError,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_exception_http(hass, user_flow):
    """Test we handle generic exception over HTTP."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", side_effect=Exception,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_form_cannot_connect_ws(hass, user_flow):
    """Test we handle cannot connect over WebSocket error."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", return_value=True,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

    with patch.object(
        MockConnection, "connect", AsyncMock(side_effect=CannotConnectError)
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(connected=False),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], TEST_WS_PORT
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping",
        side_effect=CannotConnectError,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], TEST_WS_PORT
        )

    assert result4["type"] == "form"
    assert result4["errors"] == {"base": "cannot_connect"}


async def test_form_exception_ws(hass, user_flow):
    """Test we handle generic exception over WebSocket."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", return_value=True,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_CREDENTIALS
        )

    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", side_effect=Exception,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_discovery(hass, discovery_flow):
    """Test discovery flow works."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping", return_value=True,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ), patch(
        "homeassistant.components.kodi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kodi.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            discovery_flow, TEST_CREDENTIALS
        )

        assert result["type"] == "form"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_WS_PORT
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "hostname"
    assert result2["data"] == {
        **TEST_HOST,
        **TEST_CREDENTIALS,
        **TEST_WS_PORT,
        "name": "hostname",
        "timeout": DEFAULT_TIMEOUT,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_cannot_connect_http(hass, discovery_flow):
    """Test discovery aborts if cannot connect."""
    with patch(
        "homeassistant.components.kodi.config_flow.Kodi.ping",
        side_effect=CannotConnectError,
    ), patch(
        "homeassistant.components.kodi.config_flow.get_kodi_connection",
        return_value=MockConnection(),
    ):
        result = await hass.config_entries.flow.async_configure(
            discovery_flow, TEST_CREDENTIALS
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_discovery_duplicate_data(hass, discovery_flow):
    """Test discovery aborts if same mDNS packet arrives."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass):
    """Test a duplicate discovery id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UUID,
        data={"host": "dummy", "port": 11, "namename": "dummy.local."},
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=TEST_DISCOVERY
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["port"] == 8080
    assert entry.data["name"] == "hostname"


async def test_form_import(hass):
    """Test we get the form with import source."""
    with patch(
        "homeassistant.components.kodi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kodi.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_IMPORT,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_IMPORT["name"]
    assert result["data"] == TEST_IMPORT

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
