"""Test the Grandstream Home config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
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
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GDS 00:0B:82:12:34:56"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 443,
        CONF_USERNAME: "gdsha",
        CONF_VERIFY_SSL: False,
        CONF_TYPE: "GDS",
        CONF_MODEL: None,
        ATTR_SW_VERSION: None,
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == format_mac("00:0B:82:12:34:56")


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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user flow when auth is invalid."""
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
        return_value=(False, "invalid_auth"),
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
    assert result["errors"]["base"] == "invalid_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    assert result["title"] == "GDS3710-EC74D79753C5"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 443,
        CONF_USERNAME: "gdsha",
        CONF_VERIFY_SSL: False,
        CONF_TYPE: "GDS",
        CONF_MODEL: None,
        ATTR_SW_VERSION: "1.0.1.13",
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == format_mac("EC74D79753C5")


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


@pytest.mark.parametrize(
    ("login_return", "expected_error"),
    [
        pytest.param(
            (False, "ha_control_disabled"),
            "ha_control_disabled",
            id="ha_control_disabled",
        ),
        pytest.param((False, "offline"), "cannot_connect", id="offline"),
    ],
)
async def test_user_device_error(
    hass: HomeAssistant,
    login_return: tuple,
    expected_error: str,
) -> None:
    """Test user flow when device returns error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    with patch(
        "homeassistant.components.grandstream_home.config_flow.attempt_login",
        return_value=login_return,
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
    assert result["errors"]["base"] == expected_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: "443",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_already_in_progress(hass: HomeAssistant) -> None:
    """Test zeroconf aborts when same flow already in progress."""
    zeroconf_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="GDS3710-EC74D79753C5.local.",
        name="GDS3710-EC74D79753C5._https._tcp.local.",
        port=443,
        properties={"version": "1.0.1.13"},
        type="_https._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info,
    )

    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info,
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
    assert result["title"] == "GSC4505-EC74D79753C5"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 443,
        CONF_USERNAME: "gdsha",
        CONF_VERIFY_SSL: False,
        CONF_TYPE: "GSC",
        CONF_MODEL: None,
        ATTR_SW_VERSION: "1.0.1.13",
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == format_mac("EC74D79753C5")
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == format_mac("EC74D79753C5")


@pytest.mark.parametrize(
    ("name", "hostname", "properties", "title"),
    [
        pytest.param(
            "",
            "device.local.",
            None,
            "GDS 00:0B:82:12:34:56",
            id="empty_name_no_properties",
        ),
        pytest.param(
            "GDS3710-EC74D79753C5._https._tcp.local.",
            "GDS3710-EC74D79753C5.local.",
            {},
            "GDS3710-EC74D79753C5",
            id="no_txt_properties",
        ),
        pytest.param(
            "GDS3710-EC74D79753C5._https._tcp.local.",
            "GDS3710-EC74D79753C5.local.",
            {"product": "GDS3710"},
            "GDS3710-EC74D79753C5",
            id="properties_no_version",
        ),
    ],
)
async def test_zeroconf_edge_cases(
    hass: HomeAssistant,
    name: str,
    hostname: str,
    properties: dict | None,
    title: str,
) -> None:
    """Test zeroconf flow with edge case properties."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname=hostname,
            name=name,
            port=443,
            properties=properties,
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
    assert result["title"] == title
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id is not None


async def test_user_already_configured(
    hass: HomeAssistant,
    mock_gds_api: MagicMock,
) -> None:
    """Test user flow aborts when device already configured by MAC."""
    mac = format_mac("00:0B:82:12:34:56")
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        unique_id=mac,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "gdsha",
            CONF_PASSWORD: "password",
            CONF_TYPE: "GDS",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.100"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_no_mac_already_configured(
    hass: HomeAssistant,
    mock_gds_api: MagicMock,
) -> None:
    """Test user flow aborts when no MAC and same host+port already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        unique_id="ec:74:d7:97:53:c5",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "gdsha",
            CONF_PASSWORD: "password",
            CONF_TYPE: "GDS",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )
    mock_entry.add_to_hass(hass)

    mock_gds_api.device_mac = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.100"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_no_mac_new_device(
    hass: HomeAssistant,
    mock_gds_api: MagicMock,
) -> None:
    """Test user flow creates entry with host:port unique_id when no MAC."""
    mock_gds_api.device_mac = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.200"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "192.168.1.200:443"


async def test_user_empty_host(
    hass: HomeAssistant,
) -> None:
    """Test user flow shows error and returns to user step when host is empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "missing_data"

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
