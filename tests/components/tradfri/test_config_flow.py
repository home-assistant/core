"""Test the Tradfri config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.tradfri import config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TRADFRI_PATH

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_auth")
def mock_auth_fixture():
    """Mock authenticate."""
    with patch(f"{TRADFRI_PATH}.config_flow.authenticate") as auth:
        yield auth


async def test_already_paired(hass: HomeAssistant, mock_entry_setup) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_authenticate"}


async def test_user_connection_successful(
    hass: HomeAssistant, mock_auth, mock_entry_setup
) -> None:
    """Test a successful connection."""
    mock_auth.side_effect = lambda hass, host, code: {"host": host, "gateway_id": "bla"}

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "123.123.123.123", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
    }


async def test_user_connection_timeout(
    hass: HomeAssistant, mock_auth, mock_entry_setup
) -> None:
    """Test a connection timeout."""
    mock_auth.side_effect = config_flow.AuthError("timeout")

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "127.0.0.1", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 0

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout"}


async def test_user_connection_bad_key(
    hass: HomeAssistant, mock_auth, mock_entry_setup
) -> None:
    """Test a connection with bad key."""
    mock_auth.side_effect = config_flow.AuthError("invalid_security_code")

    flow = await hass.config_entries.flow.async_init(
        "tradfri", context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "127.0.0.1", "security_code": "abcd"}
    )

    assert len(mock_entry_setup.mock_calls) == 0

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"security_code": "invalid_security_code"}


async def test_discovery_connection(
    hass: HomeAssistant, mock_auth, mock_entry_setup
) -> None:
    """Test a connection via discovery."""
    mock_auth.side_effect = lambda hass, host, code: {"host": host, "gateway_id": "bla"}

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("123.123.123.123"),
            ip_addresses=[ip_address("123.123.123.123")],
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "homekit-id"
    assert result["result"].data == {
        "host": "123.123.123.123",
        "gateway_id": "bla",
    }


async def test_discovery_duplicate_aborted(hass: HomeAssistant) -> None:
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain="tradfri", data={"host": "some-host"}, unique_id="homekit-id"
    )
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("123.123.123.124"),
            ip_addresses=[ip_address("123.123.123.124")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == "already_configured"

    assert entry.data["host"] == "123.123.123.124"


async def test_duplicate_discovery(
    hass: HomeAssistant, mock_auth, mock_entry_setup
) -> None:
    """Test a duplicate discovery in progress is ignored."""
    result = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("123.123.123.123"),
            ip_addresses=[ip_address("123.123.123.123")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("123.123.123.123"),
            ip_addresses=[ip_address("123.123.123.123")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert result2["type"] is FlowResultType.ABORT


async def test_discovery_updates_unique_id(hass: HomeAssistant) -> None:
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain="tradfri",
        data={"host": "123.123.123.123"},
    )
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        "tradfri",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("123.123.123.123"),
            ip_addresses=[ip_address("123.123.123.123")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "homekit-id"},
            type="mock_type",
        ),
    )

    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == "already_configured"

    assert entry.unique_id == "homekit-id"
