"""Tests for the WattWächter Plus config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest

from aio_wattwaechter import WattwaechterAuthenticationError, WattwaechterConnectionError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wattwaechter.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
)

from .conftest import (
    MOCK_ALIVE_RESPONSE,
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_ID,
    MOCK_DEVICE_NAME,
    MOCK_FW_VERSION,
    MOCK_HOST,
    MOCK_MAC,
    MOCK_MODEL,
    MOCK_SETTINGS,
    MOCK_SYSTEM_INFO,
    MOCK_TOKEN,
)


MOCK_ZEROCONF_DISCOVERY = type("ZeroconfServiceInfo", (), {
    "host": ip_address(MOCK_HOST),
    "port": 80,
    "hostname": "wattwaechter.local.",
    "type": "_wattwaechter._tcp.local.",
    "name": f"WWP-{MOCK_DEVICE_ID}._wattwaechter._tcp.local.",
    "properties": {
        "id": f"WWP-{MOCK_DEVICE_ID}",
        "model": MOCK_MODEL,
        "ver": MOCK_FW_VERSION,
        "mac": MOCK_MAC,
    },
})()


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock the integration setup and unload to avoid full platform loading."""
    with (
        patch(
            "custom_components.wattwaechter.async_setup_entry",
            return_value=True,
        ) as mock,
        patch(
            "custom_components.wattwaechter.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock


# --- User Flow (manual configuration) ---


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful manual configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_TOKEN: MOCK_TOKEN},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_TOKEN] == MOCK_TOKEN
    assert result["data"][CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert result["data"][CONF_DEVICE_NAME] == MOCK_DEVICE_NAME


async def test_user_flow_no_token(hass: HomeAssistant) -> None:
    """Test manual configuration without API token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] is None


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test manual configuration with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(
            side_effect=WattwaechterConnectionError("Connection refused")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test manual configuration with invalid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.system_info = AsyncMock(
            side_effect=WattwaechterAuthenticationError("Invalid token")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_TOKEN: "bad-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


# --- Reauth Flow ---


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful reauthentication with new token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "new-valid-token"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-valid-token"


async def test_reauth_flow_invalid_token(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reauthentication with invalid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(
            side_effect=WattwaechterAuthenticationError("Invalid token")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "bad-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reauthentication when device is unreachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(
            side_effect=WattwaechterConnectionError("Connection refused")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: MOCK_TOKEN},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


# --- Options Flow ---


async def test_options_flow(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow for scan interval."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"scan_interval": 60},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 60


# --- Zeroconf Flow ---


async def test_zeroconf_flow_success(hass: HomeAssistant) -> None:
    """Test successful zeroconf discovery and confirmation."""
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Confirm with token
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: MOCK_TOKEN},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_TOKEN] == MOCK_TOKEN
    assert result["data"][CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert result["data"][CONF_MODEL] == MOCK_MODEL
    assert result["data"][CONF_FW_VERSION] == MOCK_FW_VERSION
    assert result["data"][CONF_MAC] == MOCK_MAC


async def test_zeroconf_flow_no_token(hass: HomeAssistant) -> None:
    """Test zeroconf discovery confirmed without token."""
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] is None


async def test_zeroconf_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf aborts when device is unreachable."""
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(
            side_effect=WattwaechterConnectionError("Connection refused")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_invalid_auth_on_confirm(hass: HomeAssistant) -> None:
    """Test zeroconf confirm shows error on invalid token."""
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(
            side_effect=WattwaechterAuthenticationError("Invalid token")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "bad-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test zeroconf aborts when device is already configured."""
    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_no_device_id(hass: HomeAssistant) -> None:
    """Test zeroconf aborts when no device ID in TXT record."""
    discovery_no_id = type("ZeroconfServiceInfo", (), {
        "host": ip_address(MOCK_HOST),
        "port": 80,
        "hostname": "wattwaechter.local.",
        "type": "_wattwaechter._tcp.local.",
        "name": "wattwaechter._wattwaechter._tcp.local.",
        "properties": {
            "id": "",
            "model": MOCK_MODEL,
            "ver": MOCK_FW_VERSION,
            "mac": MOCK_MAC,
        },
    })()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_no_id,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_id"


# --- Reconfigure Flow ---


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful reconfiguration of host and token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200", CONF_TOKEN: "new-token"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_TOKEN] == "new-token"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reconfiguration with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(
            side_effect=WattwaechterConnectionError("Connection refused")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reconfiguration with invalid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "custom_components.wattwaechter.config_flow.Wattwaechter"
    ) as mock_cls:
        client = mock_cls.return_value
        client.system_info = AsyncMock(
            side_effect=WattwaechterAuthenticationError("Invalid token")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200", CONF_TOKEN: "bad-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"
