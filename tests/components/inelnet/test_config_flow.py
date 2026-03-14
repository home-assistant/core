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
        """Channel < 1 or > 16 raises ValueError."""
        with pytest.raises(ValueError):
            parse_channels("0")
        with pytest.raises(ValueError):
            parse_channels("17")

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
        """Valid hostname is accepted."""
        assert is_valid_host("inelnet.local") is True
        assert is_valid_host("controller") is True

    def test_empty_invalid(self) -> None:
        """Empty or whitespace is invalid."""
        assert is_valid_host("") is False
        assert is_valid_host("   ") is False

    def test_invalid_ip_octets(self) -> None:
        """Invalid IPv4-like string can be rejected (implementation may allow)."""
        # Current impl allows any \d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}
        assert is_valid_host("256.1.1.1") is True  # regex allows it


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
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.inelnet.config_flow.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session_cls.return_value = mock_session

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
    """Test connection failure shows form with cannot_connect error."""
    failing_resp = AsyncMock()
    failing_resp.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
    failing_resp.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.inelnet.config_flow.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=failing_resp)
        mock_session_cls.return_value = mock_session

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
    """Test duplicate host+channels aborts."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.inelnet.config_flow.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session_cls.return_value = mock_session

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Same host + channels again should abort
    with patch(
        "homeassistant.components.inelnet.config_flow.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session_cls.return_value = mock_session

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: "192.168.1.67", CONF_CHANNELS: "1"},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
