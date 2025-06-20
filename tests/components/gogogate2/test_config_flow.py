"""Tests for the GogoGate2 component."""

from ipaddress import ip_address
from unittest.mock import MagicMock, patch

from ismartgate import GogoGate2Api, ISmartGateApi
from ismartgate.common import ApiError
from ismartgate.const import GogoGate2ApiErrorCode

from homeassistant import config_entries
from homeassistant.components.gogogate2.const import (
    DEVICE_TYPE_GOGOGATE2,
    DEVICE_TYPE_ISMARTGATE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from . import _mocked_ismartgate_closed_door_response

from tests.common import MockConfigEntry

MOCK_MAC_ADDR = "AA:BB:CC:DD:EE:FF"


@patch("homeassistant.components.gogogate2.async_setup_entry", return_value=True)
@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_auth_fail(
    gogogate2api_mock, async_setup_entry_mock, hass: HomeAssistant
) -> None:
    """Test authorization failures."""
    api: GogoGate2Api = MagicMock(spec=GogoGate2Api)
    gogogate2api_mock.return_value = api

    api.reset_mock()
    api.async_info.side_effect = ApiError(
        GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT, "blah"
    )
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "base": "invalid_auth",
    }

    api.reset_mock()
    api.async_info.side_effect = Exception("Generic connection error.")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    api.reset_mock()
    api.async_info.side_effect = ApiError(0, "blah")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_homekit_unique_id_already_setup(hass: HomeAssistant) -> None:
    """Test that we abort from homekit if gogogate2 is already setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.2.3.4"),
            ip_addresses=[ip_address("1.2.3.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: MOCK_MAC_ADDR},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == MOCK_MAC_ADDR

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4", CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.2.3.4"),
            ip_addresses=[ip_address("1.2.3.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: MOCK_MAC_ADDR},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT


async def test_form_homekit_ip_address_already_setup(hass: HomeAssistant) -> None:
    """Test that we abort from homekit if gogogate2 is already setup."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4", CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.2.3.4"),
            ip_addresses=[ip_address("1.2.3.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: MOCK_MAC_ADDR},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT


async def test_form_homekit_ip_address(hass: HomeAssistant) -> None:
    """Test homekit includes the defaults ip address."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.2.3.4"),
            ip_addresses=[ip_address("1.2.3.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: MOCK_MAC_ADDR},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    data_schema = result["data_schema"]
    assert data_schema({CONF_USERNAME: "username", CONF_PASSWORD: "password"}) == {
        CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_PASSWORD: "password",
        CONF_USERNAME: "username",
    }


@patch("homeassistant.components.gogogate2.async_setup_entry", return_value=True)
@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_discovered_dhcp(
    ismartgateapi_mock, async_setup_entry_mock, hass: HomeAssistant
) -> None:
    """Test we get the form with homekit and abort for dhcp source when we get both."""
    api: ISmartGateApi = MagicMock(spec=ISmartGateApi)
    ismartgateapi_mock.return_value = api

    api.reset_mock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.2.3.4", macaddress=MOCK_MAC_ADDR, hostname="mock_hostname"
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result2
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    api.reset_mock()

    closed_door_response = _mocked_ismartgate_closed_door_response()
    api.async_info.return_value = closed_door_response
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result3
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        "device": "ismartgate",
        "ip_address": "1.2.3.4",
        "password": "password0",
        "username": "user0",
    }


async def test_discovered_by_homekit_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with homekit and abort for dhcp source when we get both."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.2.3.4"),
            ip_addresses=[ip_address("1.2.3.4")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: MOCK_MAC_ADDR},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.2.3.4", macaddress=MOCK_MAC_ADDR, hostname="mock_hostname"
        ),
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.2.3.4", macaddress="00:00:00:00:00:00", hostname="mock_hostname"
        ),
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"
