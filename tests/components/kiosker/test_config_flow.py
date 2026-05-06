"""Test the Kiosker config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from kiosker import (
    AuthenticationError,
    BadRequestError,
    ConnectionError,
    IPAuthenticationError,
    PingError,
    TLSVerificationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.kiosker.const import CONF_API_TOKEN, DOMAIN
from homeassistant.const import CONF_HOST, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.39"),
    ip_addresses=[ip_address("192.168.1.39")],
    hostname="python-test-device.local.",
    name="Kiosker Device._kiosker._tcp.local.",
    port=8081,
    properties={
        "uuid": "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC",
        "app": "Kiosker",
        "version": "1.0.0",
        "ssl": "true",
    },
    type="_kiosker._tcp.local.",
)

DISCOVERY_INFO_NO_UUID = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.39"),
    ip_addresses=[ip_address("192.168.1.39")],
    hostname="kiosker-device.local.",
    name="Kiosker Device._kiosker._tcp.local.",
    port=8081,
    properties={"app": "Kiosker", "version": "1.0.0", "ssl": "false"},
    type="_kiosker._tcp.local.",
)


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_kiosker_api: MagicMock,
) -> None:
    """Test the full user config flow creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_API_TOKEN: "test-token",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Kiosker A98BE1CE"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_API_TOKEN: "test-token",
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    }
    assert result2["result"].unique_id == "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ConnectionError(), "cannot_connect"),
        (AuthenticationError(), "invalid_auth"),
        (IPAuthenticationError(), "invalid_ip_auth"),
        (TLSVerificationError(), "tls_error"),
        (BadRequestError(), "bad_request"),
        (PingError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_kiosker_api: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user flow handles all validation errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_kiosker_api.status.side_effect = exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_API_TOKEN: "test-token",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    # Test that the flow recovers on retry
    mock_kiosker_api.status.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_API_TOKEN: "test-token",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
) -> None:
    """Test the zeroconf discovery happy flow creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "python-test-device (A98BE1CE)",
        "host": "192.168.1.39",
    }
    schema_keys = list(result["data_schema"].schema.keys())
    assert any(key.schema == CONF_API_TOKEN for key in schema_keys)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "test-token",
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Kiosker A98BE1CE"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.39",
        CONF_API_TOKEN: "test-token",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert result2["result"].unique_id == "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"


async def test_zeroconf_error_and_recovery(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
) -> None:
    """Test zeroconf discovery handles errors and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    mock_kiosker_api.status.side_effect = ConnectionError()
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "test-token",
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    mock_kiosker_api.status.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "test-token",
            CONF_VERIFY_SSL: False,
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_no_uuid(hass: HomeAssistant) -> None:
    """Test zeroconf discovery without UUID aborts with cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_NO_UUID,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kiosker_api: MagicMock,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_API_TOKEN: "test-token",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_zeroconf_abort_if_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf discovery if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_no_device_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_kiosker_api: MagicMock,
) -> None:
    """Test user flow shows cannot_connect error when device reports no device ID."""
    mock_kiosker_api.status.return_value.device_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.1.5",
            CONF_API_TOKEN: "test_token",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
