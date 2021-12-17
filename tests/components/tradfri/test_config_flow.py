"""Test the Tradfri config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.tradfri import config_flow

from . import TRADFRI_PATH

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_auth")
def mock_auth_fixture():
    """Mock authenticate."""
    with patch(f"{TRADFRI_PATH}.config_flow.authenticate") as auth:
        yield auth


async def test_already_paired(hass, mock_entry_setup):
    """Test Gateway already paired."""
    with patch(
        f"{TRADFRI_PATH}.config_flow.APIFactory",
        autospec=True,
    ) as mock_lib:
        mock_it = AsyncMock()
        mock_it.generate_psk.return_value = None
        mock_lib.init.return_value = mock_it
        result = await hass.config_entries.flow.async_init(
            "tradfri", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "123.123.123.123", "security_code": "abcd"}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_authenticate"}


async def test_user_connection_successful(hass, mock_auth, mock_entry_setup):
    """Test a successful connection."""
    mock_auth.side_effect = lambda hass, host, code: {"host": host, "gateway_id": "bla"}

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "123.123.123.123", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
        "import_groups": False,
    }


async def test_user_connection_timeout(hass, mock_auth, mock_entry_setup):
    """Test a connection timeout."""
    mock_auth.side_effect = config_flow.AuthError("timeout")

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "127.0.0.1", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 0

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "timeout"}


async def test_user_connection_bad_key(hass, mock_auth, mock_entry_setup):
    """Test a connection with bad key."""
    mock_auth.side_effect = config_flow.AuthError("invalid_security_code")

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "127.0.0.1", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 0

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"security_code": "invalid_security_code"}


async def test_discovery_connection(hass, mock_auth, mock_entry_setup):
    """Test a connection via discovery."""
    mock_auth.side_effect = lambda hass, host, code: {"host": host, "gateway_id": "bla"}

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            host="123.123.123.123",
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == "homekit-id"
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
        "import_groups": False,
    }


async def test_import_connection(hass, mock_auth, mock_entry_setup):
    """Test a connection via import."""
    mock_auth.side_effect = lambda hass, host, code: {
        "host": host,
        "gateway_id": "bla",
        "identity": "mock-iden",
        "key": "mock-key",
    }

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": "123.123.123.123", "import_groups": True},
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"security_code": "abcd"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
        "identity": "mock-iden",
        "key": "mock-key",
        "import_groups": True,
    }

    assert len(mock_entry_setup.mock_calls) == 1


async def test_import_connection_no_groups(hass, mock_auth, mock_entry_setup):
    """Test a connection via import and no groups allowed."""
    mock_auth.side_effect = lambda hass, host, code: {
        "host": host,
        "gateway_id": "bla",
        "identity": "mock-iden",
        "key": "mock-key",
    }

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": "123.123.123.123", "import_groups": False},
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"security_code": "abcd"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
        "identity": "mock-iden",
        "key": "mock-key",
        "import_groups": False,
    }

    assert len(mock_entry_setup.mock_calls) == 1


async def test_import_connection_legacy(hass, mock_gateway_info, mock_entry_setup):
    """Test a connection via import."""
    mock_gateway_info.side_effect = lambda hass, host, identity, key: {
        "host": host,
        "identity": identity,
        "key": key,
        "gateway_id": "mock-gateway",
    }

    result = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": "123.123.123.123", "key": "mock-key", "import_groups": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "mock-gateway",
        "identity": "homeassistant",
        "key": "mock-key",
        "import_groups": True,
    }

    assert len(mock_gateway_info.mock_calls) == 1
    assert len(mock_entry_setup.mock_calls) == 1


async def test_import_connection_legacy_no_groups(
    hass, mock_gateway_info, mock_entry_setup
):
    """Test a connection via legacy import and no groups allowed."""
    mock_gateway_info.side_effect = lambda hass, host, identity, key: {
        "host": host,
        "identity": identity,
        "key": key,
        "gateway_id": "mock-gateway",
    }

    result = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": "123.123.123.123", "key": "mock-key", "import_groups": False},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "mock-gateway",
        "identity": "homeassistant",
        "key": "mock-key",
        "import_groups": False,
    }

    assert len(mock_gateway_info.mock_calls) == 1
    assert len(mock_entry_setup.mock_calls) == 1


async def test_discovery_duplicate_aborted(hass):
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain="tradfri", data={"host": "some-host"}, unique_id="homekit-id"
    )
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            host="new-host",
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert flow["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert flow["reason"] == "already_configured"

    assert entry.data["host"] == "new-host"


async def test_import_duplicate_aborted(hass):
    """Test a duplicate import host is ignored."""
    MockConfigEntry(domain="tradfri", data={"host": "some-host"}).add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": "some-host"},
    )

    assert flow["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert flow["reason"] == "already_configured"


async def test_duplicate_discovery(hass, mock_auth, mock_entry_setup):
    """Test a duplicate discovery in progress is ignored."""
    result = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            host="123.123.123.123",
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            host="123.123.123.123",
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_discovery_updates_unique_id(hass):
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain="tradfri",
        data={"host": "some-host"},
    )
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            host="some-host",
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert flow["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert flow["reason"] == "already_configured"

    assert entry.unique_id == "homekit-id"
