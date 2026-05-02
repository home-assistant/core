"""Tests for Wibeee config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.wibeee.config_flow import (
    _async_configure_device,
    _get_ha_port,
    _get_local_ip,
    _get_local_ip_sync,
    _is_routable_ip,
)
from homeassistant.components.wibeee.const import (
    CONF_AUTO_CONFIGURE,
    CONF_UPDATE_MODE,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_HOST, MOCK_MAC

from tests.common import MockConfigEntry


async def test_user_step_shows_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the user step shows a form with host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_validates_and_goes_to_mode(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test user step validates device and moves to mode step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mode"


async def test_user_step_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test user step handles connection error."""
    # validate_input calls async_fetch_device_info
    mock_wibeee_api_config_flow.async_fetch_device_info.side_effect = TimeoutError(
        "error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert "errors" in result
    assert result["errors"][CONF_HOST] == "no_device_info"


async def test_user_step_invalid_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test user step handles non-Wibeee device."""
    mock_wibeee_api_config_flow.async_fetch_device_info.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "no_device_info"


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test DHCP discovery flow."""
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mode"


async def test_mode_step_creates_entry_polling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test mode step creates entry with polling mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UPDATE_MODE: MODE_POLLING},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["options"][CONF_UPDATE_MODE] == MODE_POLLING


async def test_mode_step_creates_entry_push(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test mode step creates entry with local push mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        return_value="192.168.1.50",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_UPDATE_MODE: MODE_LOCAL_PUSH, CONF_AUTO_CONFIGURE: False},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["options"][CONF_UPDATE_MODE] == MODE_LOCAL_PUSH


async def test_mode_step_auto_configure_fail(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test mode step handles auto-configuration failure."""
    mock_wibeee_api_config_flow.async_configure_push_server.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        return_value="192.168.1.50",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_UPDATE_MODE: MODE_LOCAL_PUSH, CONF_AUTO_CONFIGURE: True},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "auto_configure_failed"


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UPDATE_MODE: MODE_POLLING,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options[CONF_UPDATE_MODE] == MODE_POLLING


async def test_options_flow_auto_configure_fail(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test options flow handles auto-configuration failure."""
    # Ensure the instance used in options flow is mocked
    mock_wibeee_api.async_configure_push_server.return_value = False

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        return_value="192.168.1.50",
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_UPDATE_MODE: MODE_LOCAL_PUSH,
                CONF_AUTO_CONFIGURE: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "auto_configure_failed"


async def test_reconfigure_step_success(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test reconfigure step updates the host successfully."""
    new_host = "192.168.1.200"

    result = await loaded_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: new_host},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert loaded_entry.data[CONF_HOST] == new_host


async def test_reconfigure_step_wrong_device(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test reconfigure aborts when a different device is reached."""
    different_mac = "aabbccddeeff"
    device_info = mock_wibeee_api_config_flow.async_fetch_device_info.return_value
    device_info.mac_addr = different_mac
    device_info.mac_addr_formatted = different_mac.upper()

    result = await loaded_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.250"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_reconfigure_step_no_device_info(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test reconfigure shows error when device cannot be reached."""
    mock_wibeee_api_config_flow.async_fetch_device_info.side_effect = TimeoutError(
        "error"
    )

    result = await loaded_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.250"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "no_device_info"


# -- Helper function tests (no fixtures that mock the helpers) --


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("192.168.1.1", True),
        ("10.0.0.5", True),
        ("8.8.8.8", True),
        ("127.0.0.1", False),
        ("169.254.1.1", False),
        ("224.0.0.1", False),
        ("0.0.0.0", False),
        ("not-an-ip", False),
        ("999.999.999.999", False),
    ],
)
def test_is_routable_ip(ip: str, expected: bool) -> None:
    """Test _is_routable_ip classifies addresses correctly."""
    assert _is_routable_ip(ip) is expected


def test_get_local_ip_sync_success() -> None:
    """Test _get_local_ip_sync returns the socket-derived IP."""
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("192.168.1.55", 12345)
    with patch(
        "homeassistant.components.wibeee.config_flow.socket.socket",
        return_value=fake_sock,
    ):
        assert _get_local_ip_sync() == "192.168.1.55"
    fake_sock.connect.assert_called_once()
    fake_sock.close.assert_called_once()


def test_get_local_ip_sync_oserror_fallback() -> None:
    """Test _get_local_ip_sync falls back to loopback on OSError."""
    fake_sock = MagicMock()
    fake_sock.connect.side_effect = OSError("network unreachable")
    with patch(
        "homeassistant.components.wibeee.config_flow.socket.socket",
        return_value=fake_sock,
    ):
        assert _get_local_ip_sync() == "127.0.0.1"
    fake_sock.close.assert_called_once()


async def test_get_local_ip_uses_async_get_source_ip(hass: HomeAssistant) -> None:
    """Test _get_local_ip returns the IP from network.async_get_source_ip."""
    # Disable the autouse fixture by calling the real function directly.
    with patch(
        "homeassistant.components.network.async_get_source_ip",
        new_callable=AsyncMock,
        return_value="10.0.0.42",
    ):
        # Call the real _get_local_ip, bypassing autouse mock
        result = (
            await _get_local_ip.__wrapped__(hass)
            if hasattr(_get_local_ip, "__wrapped__")
            else await _get_local_ip(hass)
        )
    assert result == "10.0.0.42"


async def test_get_local_ip_falls_back_to_get_url(hass: HomeAssistant) -> None:
    """Test _get_local_ip falls back to get_url when async_get_source_ip fails."""
    with (
        patch(
            "homeassistant.components.network.async_get_source_ip",
            new_callable=AsyncMock,
            side_effect=HomeAssistantError("no network"),
        ),
        patch(
            "homeassistant.helpers.network.get_url",
            return_value="http://192.168.1.77:8123",
        ),
    ):
        result = await _get_local_ip(hass)
    assert result == "192.168.1.77"


async def test_get_local_ip_uses_executor_fallback(hass: HomeAssistant) -> None:
    """Test _get_local_ip falls back to socket-based detection."""
    with (
        patch(
            "homeassistant.components.network.async_get_source_ip",
            new_callable=AsyncMock,
            side_effect=HomeAssistantError("no network"),
        ),
        patch(
            "homeassistant.helpers.network.get_url",
            side_effect=HomeAssistantError("no url"),
        ),
        patch(
            "homeassistant.components.wibeee.config_flow._get_local_ip_sync",
            return_value="192.168.1.99",
        ),
    ):
        result = await _get_local_ip(hass)
    assert result == "192.168.1.99"


async def test_get_ha_port_from_url(hass: HomeAssistant) -> None:
    """Test _get_ha_port returns port from get_url."""
    with patch(
        "homeassistant.helpers.network.get_url",
        return_value="http://192.168.1.10:9999",
    ):
        assert _get_ha_port(hass) == 9999


async def test_get_ha_port_default_on_error(hass: HomeAssistant) -> None:
    """Test _get_ha_port returns default on HomeAssistantError."""
    with patch(
        "homeassistant.helpers.network.get_url",
        side_effect=HomeAssistantError("boom"),
    ):
        assert _get_ha_port(hass) == 8123


async def test_async_configure_device_non_routable_ip(hass: HomeAssistant) -> None:
    """Test _async_configure_device returns False for non-routable local IP."""
    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        new_callable=AsyncMock,
        return_value="127.0.0.1",
    ):
        assert await _async_configure_device(hass, "192.168.1.100") is False


async def test_async_configure_device_timeout(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test _async_configure_device returns False when API times out."""
    mock_wibeee_api.async_configure_push_server.side_effect = TimeoutError("t")
    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        new_callable=AsyncMock,
        return_value="192.168.1.50",
    ):
        assert await _async_configure_device(hass, "192.168.1.100") is False


async def test_async_configure_device_success(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test _async_configure_device returns True on success."""
    mock_wibeee_api.async_configure_push_server.return_value = True
    with patch(
        "homeassistant.components.wibeee.config_flow._get_local_ip",
        new_callable=AsyncMock,
        return_value="192.168.1.50",
    ):
        assert await _async_configure_device(hass, "192.168.1.100") is True


# -- DHCP and exception-path tests --


async def test_dhcp_already_configured_updates_host(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = DhcpServiceInfo(
        ip="192.168.1.250",
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_not_wibeee_device(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test DHCP discovery aborts when device is not a Wibeee."""
    mock_wibeee_api.async_check_connection.return_value = False
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="not_wibeee",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_wibeee_device"


async def test_dhcp_connection_error(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test DHCP discovery aborts when connection fails."""
    mock_wibeee_api.async_check_connection.side_effect = aiohttp.ClientError("boom")
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_wibeee_device"


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user step aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_unexpected_exception(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test user step shows generic error on unexpected exception."""
    mock_wibeee_api.async_fetch_device_info.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_reconfigure_step_unexpected_exception(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test reconfigure step shows generic error on unexpected exception."""
    mock_wibeee_api.async_fetch_device_info.side_effect = RuntimeError("boom")

    result = await loaded_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.250"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
