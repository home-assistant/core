"""Test the Qube Heat Pump config flow."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.qube_heatpump.config_flow import _async_resolve_host
from homeassistant.components.qube_heatpump.const import CONF_HOST, CONF_PORT, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=f"{DOMAIN}-1.2.3.4-502",
        title="Qube Heat Pump (1.2.3.4)",
    )


async def test_form(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        return_value=(AsyncMock(), MagicMock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Qube Heat Pump (1.2.3.4)"
    assert result2["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 502,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        side_effect=OSError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test we get duplicate_ip error when same host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=f"{DOMAIN}-1.2.3.4-502",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        return_value=(AsyncMock(), MagicMock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    # Config flow returns form with duplicate_ip error when same host is configured
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"host": "duplicate_ip"}


async def test_form_duplicate_ip(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test we handle duplicate IP error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=f"{DOMAIN}-1.2.3.4-502",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Try to configure with a hostname that resolves to the same IP
    with (
        patch(
            "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
            return_value=(AsyncMock(), MagicMock()),
        ),
        patch(
            "homeassistant.components.qube_heatpump.config_flow._async_resolve_host",
            return_value="1.2.3.4",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "qube.local"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"host": "duplicate_ip"}


async def test_form_with_existing_entries(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test the form when there are already existing entries (no default value)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=f"{DOMAIN}-1.2.3.4-502",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"


async def test_reconfigure_confirm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure confirmation updates entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow._async_resolve_host",
        return_value="5.6.7.8",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "5.6.7.8", CONF_PORT: 502},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigured"
    assert mock_config_entry.data[CONF_HOST] == "5.6.7.8"


async def test_reconfigure_unknown_entry(hass: HomeAssistant) -> None:
    """Test reconfigure aborts when entry is unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": "nonexistent_entry",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_entry"


async def test_reconfigure_duplicate_unique_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when new unique_id conflicts."""
    mock_config_entry.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8", CONF_PORT: 502},
        unique_id=f"{DOMAIN}-5.6.7.8-502",
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow._async_resolve_host",
        return_value="5.6.7.8",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "5.6.7.8", CONF_PORT: 502},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_duplicate_ip(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when new IP conflicts."""
    mock_config_entry.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "otherhost.local", CONF_PORT: 503},
        unique_id=f"{DOMAIN}-otherhost.local-503",
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow._async_resolve_host",
        side_effect=lambda h: "9.9.9.9",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "newhost.local", CONF_PORT: 503},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "duplicate_ip"


async def test_resolve_host_empty(hass: HomeAssistant) -> None:
    """Test empty host returns None."""
    result = await _async_resolve_host("")
    assert result is None


async def test_resolve_host_ip_address(hass: HomeAssistant) -> None:
    """Test IP address returns itself."""
    result = await _async_resolve_host("192.168.1.1")
    assert result == "192.168.1.1"


async def test_resolve_host_dns_failure(hass: HomeAssistant) -> None:
    """Test DNS resolution failure returns None."""
    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.get_running_loop"
    ) as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(side_effect=OSError)
        result = await _async_resolve_host("invalid.host")

    assert result is None


async def test_resolve_host_ipv6_mapped(hass: HomeAssistant) -> None:
    """Test IPv6 mapped address is converted."""
    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.get_running_loop"
    ) as mock_loop:
        # Return IPv6 mapped address
        mock_loop.return_value.getaddrinfo = AsyncMock(
            return_value=[
                (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::ffff:1.2.3.4", 0))
            ]
        )
        result = await _async_resolve_host("test.host")

    assert result == "1.2.3.4"


async def test_resolve_host_ipv4(hass: HomeAssistant) -> None:
    """Test regular IPv4 resolution."""
    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.get_running_loop"
    ) as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.2.3.4", 0))]
        )
        result = await _async_resolve_host("test.host")

    assert result == "1.2.3.4"


async def test_resolve_host_empty_sockaddr(hass: HomeAssistant) -> None:
    """Test empty sockaddr returns None."""
    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.get_running_loop"
    ) as mock_loop:
        # Return result with empty sockaddr
        mock_loop.return_value.getaddrinfo = AsyncMock(
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ())]
        )
        result = await _async_resolve_host("test.host")

    assert result is None
