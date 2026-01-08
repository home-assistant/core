"""Tests the Indevolt config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.indevolt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import TEST_DEVICE_SN_GEN2, TEST_FW_VERSION, TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user-initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"INDEVOLT CMS-SF2000 ({TEST_HOST})"
    assert result["data"]["host"] == TEST_HOST
    assert result["data"]["port"] == TEST_PORT
    assert result["data"]["sn"] == TEST_DEVICE_SN_GEN2
    assert result["data"]["fw_version"] == TEST_FW_VERSION
    assert result["data"]["device_model"] == "CMS-SF2000"
    assert result["data"]["generation"] == 2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test connection errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_user_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate entry aborts the flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Test successful reconfiguration flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_host = "192.168.1.200"
    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": new_host, "port": TEST_PORT},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data["host"] == new_host


async def test_reconfigure_wrong_device(hass: HomeAssistant) -> None:
    """Test reconfiguration aborts if device serial changes."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": "DIFFERENT_SN",
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.200", "port": TEST_PORT},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_reconfigure_error(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test error handling in reconfiguration flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery with valid config
    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_zeroconf_flow_success(hass: HomeAssistant) -> None:
    """Test successful zeroconf discovery flow."""
    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address(TEST_HOST),
                ip_addresses=[ip_address(TEST_HOST)],
                name="indevolt-12345678._http._tcp.local.",
                port=TEST_PORT,
                hostname="indevolt-12345678.local.",
                type="_http._tcp.local.",
                properties={},
            ),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["host"] == TEST_HOST
    assert result["description_placeholders"]["type"] == "CMS-SF2000"

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"INDEVOLT CMS-SF2000 ({TEST_HOST})"
    assert result["data"]["host"] == TEST_HOST
    assert result["data"]["port"] == TEST_PORT
    assert result["data"]["sn"] == TEST_DEVICE_SN_GEN2


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf aborts if already configured but updates host."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address(TEST_HOST),
                ip_addresses=[ip_address(TEST_HOST)],
                name="indevolt-12345678._http._tcp.local.",
                port=TEST_PORT,
                hostname="indevolt-12345678.local.",
                type="_http._tcp.local.",
                properties={},
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_ip_change(hass: HomeAssistant) -> None:
    """Test zeroconf updates config entry IP if changed."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDEVOLT CMS-SF2000 (192.168.1.100)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN_GEN2,
            "fw_version": TEST_FW_VERSION,
            "device_model": "CMS-SF2000",
            "generation": 2,
        },
        unique_id=f"CMS-SF2000_{TEST_DEVICE_SN_GEN2}",
    )
    mock_entry.add_to_hass(hass)
    assert mock_entry.data["host"] == TEST_HOST

    new_host = "192.168.1.200"
    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        return_value={
            "device": {
                "sn": TEST_DEVICE_SN_GEN2,
                "fw": TEST_FW_VERSION,
                "type": "CMS-SF2000",
                "generation": 2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address(new_host),
                ip_addresses=[ip_address(new_host)],
                name="indevolt-12345678._http._tcp.local.",
                port=TEST_PORT,
                hostname="indevolt-12345678.local.",
                type="_http._tcp.local.",
                properties={},
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_entry.data["host"] == new_host


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (TimeoutError, "cannot_connect"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
    ],
)
async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, exception: Exception, reason: str
) -> None:
    """Test zeroconf aborts on connection errors."""
    with patch(
        "homeassistant.components.indevolt.config_flow.IndevoltAPI.get_config",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address(TEST_HOST),
                ip_addresses=[ip_address(TEST_HOST)],
                name="indevolt-12345678._http._tcp.local.",
                port=TEST_PORT,
                hostname="indevolt-12345678.local.",
                type="_http._tcp.local.",
                properties={},
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
