"""Tests for Wibeee config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
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
