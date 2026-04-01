"""Tests for the FortiOS config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import aiohttp

from homeassistant.components.fortios.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MOCK_USER_INPUT = {
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 443,
    CONF_TOKEN: "test_token",
    "vdom": "root",
    CONF_VERIFY_SSL: False,
}

MOCK_STATUS_RESPONSE = {
    "version": "7.0.0",
    "serial": "FGT1234567890",
    "results": {},
}


def _mock_api(
    response: dict | None = None, side_effect: Exception | None = None
) -> AsyncMock:
    """Return a mocked FortiOSAPI instance."""
    mock = AsyncMock()
    if side_effect is not None:
        mock.get.side_effect = side_effect
    else:
        mock.get.return_value = response or MOCK_STATUS_RESPONSE
    return mock


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry on success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FortiGate FGT1234567890"
    assert result["data"] == MOCK_USER_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the user flow shows error when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(side_effect=Exception("Connection refused")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown_error"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test the user flow shows error on 401 Unauthorized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    error = aiohttp.ClientResponseError(None, None, status=401)
    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect_http_error(hass: HomeAssistant) -> None:
    """Test the user flow shows cannot_connect on non-401 HTTP errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    error = aiohttp.ClientResponseError(None, None, status=500)
    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unsupported_version(hass: HomeAssistant) -> None:
    """Test the user flow shows error when FortiOS version is too old."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(response={"version": "6.0.0", "serial": "FGT000"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_version"}


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test the user flow aborts when the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="FGT1234567890",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_step(hass: HomeAssistant) -> None:
    """Test the zeroconf discovery step shows user form."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("1.2.3.4"),
        ip_addresses=[ip_address("1.2.3.4")],
        hostname="fortigate.local.",
        name="fortigate._https._tcp.local.",
        port=443,
        properties={},
        type="_https._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Verify host and port are pre-filled in the schema defaults
    schema_keys = {k.schema: k for k in result["data_schema"].schema}
    assert schema_keys[CONF_HOST].default() == "1.2.3.4"
    assert schema_keys[CONF_PORT].default() == 443


async def test_zeroconf_step_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts when the IP is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("1.2.3.4"),
        ip_addresses=[ip_address("1.2.3.4")],
        hostname="fortigate.local.",
        name="fortigate._https._tcp.local.",
        port=443,
        properties={},
        type="_https._tcp.local.",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_step(hass: HomeAssistant) -> None:
    """Test the DHCP discovery step shows user form with pre-filled host."""
    # DhcpServiceInfo requires lowercase MAC without colons
    discovery_info = DhcpServiceInfo(
        ip="1.2.3.4",
        macaddress="00090f123456",
        hostname="fortigate",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    schema_keys = {k.schema: k for k in result["data_schema"].schema}
    assert schema_keys[CONF_HOST].default() == "1.2.3.4"


async def test_dhcp_step_already_configured(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when the MAC is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00090f123456",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    discovery_info = DhcpServiceInfo(
        ip="1.2.3.4",
        macaddress="00090f123456",
        hostname="fortigate",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_step(hass: HomeAssistant) -> None:
    """Test the reconfigure step updates entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="FGT1234567890",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Current values should be pre-filled
    schema_keys = {k.schema: k for k in result["data_schema"].schema}
    assert schema_keys[CONF_HOST].default() == "1.2.3.4"
    assert schema_keys[CONF_TOKEN].default() == "test_token"

    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_USER_INPUT, CONF_HOST: "5.6.7.8", CONF_TOKEN: "new_token"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "5.6.7.8"
    assert entry.data[CONF_TOKEN] == "new_token"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test the reauthentication flow updates the token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="FGT1234567890",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "new_token"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "new_token"


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test the reauthentication flow shows error on invalid token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="FGT1234567890",
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    error = aiohttp.ClientResponseError(None, None, status=401)
    with patch(
        "homeassistant.components.fortios.config_flow.FortiOSAPI",
        return_value=_mock_api(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "bad_token"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
