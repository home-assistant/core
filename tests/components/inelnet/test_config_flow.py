"""Tests for INELNET Blinds config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.inelnet.config_flow import is_valid_host, parse_channels
from homeassistant.components.inelnet.const import CONF_CHANNELS, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class TestParseChannels:
    """Tests for parse_channels helper."""

    def test_single_channel(self) -> None:
        """Parse a single channel."""
        assert parse_channels("1") == [1]

    def test_multiple_channels(self) -> None:
        """Parse comma-separated channels."""
        assert parse_channels("1,2,3") == [1, 2, 3]
        assert parse_channels("3, 1, 2") == [1, 2, 3]

    def test_sorts_channels(self) -> None:
        """Channels are returned sorted."""
        assert parse_channels("4,2,1,3") == [1, 2, 3, 4]

    def test_empty_raises(self) -> None:
        """Empty or whitespace-only raises ValueError."""
        with pytest.raises(ValueError):
            parse_channels("")
        with pytest.raises(ValueError):
            parse_channels("   ")

    def test_invalid_number_raises(self) -> None:
        """Non-numeric part raises ValueError."""
        with pytest.raises(ValueError):
            parse_channels("1,a,3")

    def test_out_of_range_raises(self) -> None:
        """Channel < 1 raises ValueError."""
        with pytest.raises(ValueError):
            parse_channels("0")
        with pytest.raises(ValueError):
            parse_channels("-1")

    def test_duplicate_raises(self) -> None:
        """Duplicate channel raises ValueError."""
        with pytest.raises(ValueError):
            parse_channels("1,2,1")


class TestIsValidHost:
    """Tests for is_valid_host helper."""

    def test_valid_ipv4(self) -> None:
        """Valid IPv4 is accepted."""
        assert is_valid_host("192.168.1.67") is True
        assert is_valid_host("10.0.0.1") is True

    def test_valid_hostname(self) -> None:
        """Valid hostname is accepted (hostname regex branch)."""
        assert is_valid_host("inelnet.local") is True
        assert is_valid_host("controller") is True
        assert is_valid_host("my.controller.local") is True

    def test_empty_invalid(self) -> None:
        """Empty or whitespace is invalid."""
        assert is_valid_host("") is False
        assert is_valid_host("   ") is False

    def test_invalid_ip_octets(self) -> None:
        """Invalid IPv4 octet (>255) is rejected."""
        assert is_valid_host("256.1.1.1") is False

    def test_valid_ipv6(self) -> None:
        """Valid IPv6 is accepted."""
        assert is_valid_host("::1") is True
        assert is_valid_host("2001:db8::1") is True

    def test_invalid_hostname_returns_false(self) -> None:
        """Non-empty host that is neither IPv4 nor valid hostname returns False."""
        assert is_valid_host("-leading-hyphen") is False
        assert is_valid_host(".leading-dot") is False
        assert is_valid_host("has space") is False
        assert is_valid_host("underscore_not_allowed") is False


async def test_config_flow_user_step_form(
    hass: HomeAssistant,
) -> None:
    """Test the user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_HOST in result["data_schema"].schema
    assert CONF_CHANNELS in result["data_schema"].schema


async def test_config_flow_create_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful config flow creates entry."""
    with patch(
        "homeassistant.components.inelnet.config_flow.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        MockChannel.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1,2"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INELNET 192.168.1.67 (ch 1,2)"
    assert result["data"][CONF_HOST] == "192.168.1.67"
    assert result["data"][CONF_CHANNELS] == [1, 2]


async def test_config_flow_invalid_host_shows_error(
    hass: HomeAssistant,
) -> None:
    """Test invalid host shows form with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "", CONF_CHANNELS: "1"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_host"


async def test_config_flow_invalid_channels_shows_error(
    hass: HomeAssistant,
) -> None:
    """Test invalid channels shows form with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "a,b"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_channels"


async def test_config_flow_cannot_connect_shows_error(
    hass: HomeAssistant,
) -> None:
    """Test ping raising shows form with cannot_connect error."""
    with patch(
        "homeassistant.components.inelnet.config_flow.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(side_effect=OSError("Connection refused"))
        MockChannel.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_create_entry_with_hostname(
    hass: HomeAssistant,
) -> None:
    """Test successful config flow with hostname (covers hostname validation branch)."""
    with patch(
        "homeassistant.components.inelnet.config_flow.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        MockChannel.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "controller.local", CONF_CHANNELS: "1"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "controller.local"


async def test_config_flow_ping_fails_shows_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test that ping returning False shows cannot_connect."""
    with patch(
        "homeassistant.components.inelnet.config_flow.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=False)
        MockChannel.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_duplicate_aborts(
    hass: HomeAssistant,
) -> None:
    """Test duplicate host+channels aborts when already configured."""
    mock_client = MagicMock()
    mock_client.ping = AsyncMock(return_value=True)
    with patch(
        "homeassistant.components.inelnet.config_flow.InelnetChannel",
        return_value=mock_client,
    ):
        first_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        first_result = await hass.config_entries.flow.async_configure(
            first_result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )
        assert first_result["type"] is FlowResultType.CREATE_ENTRY
        second_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        second_result = await hass.config_entries.flow.async_configure(
            second_result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )
    assert second_result["type"] is FlowResultType.ABORT
    assert second_result["reason"] == "already_configured"
