"""Tests for Wibeee config flow."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.wibeee.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import EXPECTED_DATA, MOCK_HOST, MOCK_MAC, build_device_info

from tests.common import MockConfigEntry


async def test_user_step_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test the user step shows a form, validates the device and creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["result"].unique_id == MOCK_MAC


@pytest.mark.parametrize(
    ("prepare_error", "clear_error", "error_key", "error_value"),
    [
        pytest.param(
            lambda api: setattr(
                api.async_fetch_device_info, "side_effect", TimeoutError("error")
            ),
            lambda api: setattr(api.async_fetch_device_info, "side_effect", None),
            CONF_HOST,
            "no_device_info",
            id="connection_error",
        ),
        pytest.param(
            lambda api: setattr(api.async_fetch_device_info, "return_value", None),
            lambda api: setattr(
                api.async_fetch_device_info,
                "return_value",
                build_device_info(),
            ),
            CONF_HOST,
            "no_device_info",
            id="invalid_device",
        ),
        pytest.param(
            lambda api: setattr(
                api.async_fetch_device_info, "side_effect", RuntimeError("boom")
            ),
            lambda api: setattr(api.async_fetch_device_info, "side_effect", None),
            "base",
            "unknown",
            id="unexpected_exception",
        ),
    ],
)
async def test_user_step_recovers_from_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api: AsyncMock,
    prepare_error: Callable[[AsyncMock], None],
    clear_error: Callable[[AsyncMock], None],
    error_key: str,
    error_value: str,
) -> None:
    """Test the user step shows an error and recovers to create the entry."""
    prepare_error(mock_wibeee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"][error_key] == error_value

    clear_error(mock_wibeee_api)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == EXPECTED_DATA
    assert result["result"].unique_id == MOCK_MAC


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test DHCP discovery shows a confirmation form and creates an entry."""
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
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == EXPECTED_DATA
    assert result["result"].unique_id == MOCK_MAC


async def test_dhcp_discovery_confirm_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test DHCP discovery aborts when the device stops responding on confirm."""
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
    assert result["step_id"] == "discovery_confirm"

    mock_wibeee_api.async_fetch_device_info.side_effect = TimeoutError("error")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_already_configured_updates_host(
    hass: HomeAssistant,
    mock_wibeee_api: AsyncMock,
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
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.250"


async def test_dhcp_not_wibeee_device(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
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


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_wibeee_api: AsyncMock,
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


async def test_dhcp_discovery_confirm_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP confirm aborts when the device gets configured meanwhile."""
    discovery_info = DhcpServiceInfo(
        ip="192.168.1.250",
        macaddress="ffeeddccbbaa",
        hostname="wibeee_test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
