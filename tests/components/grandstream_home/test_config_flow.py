"""Test the Grandstream Home config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.config_flow import GrandstreamConfigFlow
from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_gds_api")


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] is not None
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PASSWORD] == "password"


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    with patch(
        "homeassistant.components.grandstream_home.config_flow.attempt_login",
        side_effect=OSError("Connection refused"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.attempt_login",
        return_value=(False, "invalid_auth"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "wrong_password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_full_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test the zeroconf flow from discovery to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"version": "1.0.1.13"},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf aborts when device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"version": "1.0.1.13"},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test user flow when HA control is disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.attempt_login",
        return_value=(False, "ha_control_disabled"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "ha_control_disabled"


async def test_user_offline(hass: HomeAssistant) -> None:
    """Test user flow when device is offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.attempt_login",
        return_value=(False, "offline"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_zeroconf_already_in_progress(hass: HomeAssistant) -> None:
    """Test zeroconf aborts when same flow already in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"version": "1.0.1.13"},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"version": "1.0.1.13"},
            type="_https._tcp.local.",
        ),
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_zeroconf_gsc_device(hass: HomeAssistant) -> None:
    """Test zeroconf flow with a GSC device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GSC4505-EC74D79753C5.local.",
            name="GSC4505-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"version": "1.0.1.13"},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["type"] == "GSC"


async def test_zeroconf_empty_name(
    hass: HomeAssistant, mock_gds_api: MagicMock
) -> None:
    """Test zeroconf flow with empty service name and no MAC."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="device.local.",
            name="",
            port=443,
            properties=None,
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_no_txt_properties(hass: HomeAssistant) -> None:
    """Test zeroconf flow with no txt properties."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_properties_no_version(hass: HomeAssistant) -> None:
    """Test zeroconf flow with properties but no version key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="GDS3710-EC74D79753C5.local.",
            name="GDS3710-EC74D79753C5._https._tcp.local.",
            port=443,
            properties={"product": "GDS3710"},
            type="_https._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_port(hass: HomeAssistant) -> None:
    """Test auth step with invalid port number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.validate_port",
        return_value=(False, 0),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "999999",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["port"] == "invalid_port"


async def test_user_no_device_mac(hass: HomeAssistant, mock_gds_api: MagicMock) -> None:
    """Test user flow when device has no MAC address."""
    mock_gds_api.device_mac = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_validate_credentials_missing_host(hass: HomeAssistant) -> None:
    """Test _validate_credentials returns error when host is not set."""
    flow = GrandstreamConfigFlow()
    flow.hass = hass
    # _host is None by default from __init__
    api, error = await flow._validate_credentials("gdsha", "password", 443, False)
    assert api is None
    assert error == "missing_data"


async def test_auth_no_api(hass: HomeAssistant) -> None:
    """Test auth step sets fallback name when API is unavailable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.GrandstreamConfigFlow._validate_credentials",
        return_value=(None, None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "password",
                CONF_PORT: "443",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Grandstream Device"
