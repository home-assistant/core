"""Test the Lutron Caseta config flow."""
from pylutron_caseta.smartbridge import Smartbridge

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.lutron_caseta import DOMAIN
import homeassistant.components.lutron_caseta.config_flow as CasetaConfigFlow
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    ERROR_CANNOT_CONNECT,
    STEP_IMPORT_FAILED,
)
from homeassistant.const import CONF_HOST

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    def __init__(self, can_connect=True):
        """Initialize MockBridge instance with configured mock connectivity."""
        self.can_connect = can_connect
        self.is_currently_connected = False

    async def connect(self):
        """Connect the mock bridge."""
        if self.can_connect:
            self.is_currently_connected = True

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False


async def test_bridge_import_flow(hass):
    """Test a bridge entry gets created and set up during the import flow."""

    entry_mock_data = {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ), patch.object(
        Smartbridge, "create_tls"
    ) as create_tls:
        create_tls.return_value = MockBridge(can_connect=True)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == CasetaConfigFlow.ENTRY_DEFAULT_TITLE
    assert result["data"] == entry_mock_data
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bridge_cannot_connect(hass):
    """Test checking for connection and cannot_connect error."""

    entry_mock_data = {
        CONF_HOST: "not.a.valid.host",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch.object(Smartbridge, "create_tls") as create_tls:
        create_tls.return_value = MockBridge(can_connect=False)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == "form"
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_bridge_cannot_connect_unknown_error(hass):
    """Test checking for connection and encountering an unknown error."""

    entry_mock_data = {
        CONF_HOST: "",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch.object(Smartbridge, "create_tls") as create_tls:
        mock_bridge = MockBridge()
        mock_bridge.connect = AsyncMock(side_effect=Exception())
        create_tls.return_value = mock_bridge
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == "form"
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_duplicate_bridge_import(hass):
    """Test that creating a bridge entry with a duplicate host errors."""

    entry_mock_data = {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, data=entry_mock_data)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        # Mock entry added, try initializing flow with duplicate host
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_ALREADY_CONFIGURED
    assert len(mock_setup_entry.mock_calls) == 0
