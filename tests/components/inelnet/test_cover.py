"""Tests for INELNET Blinds cover platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.inelnet.const import (
    ACT_DOWN,
    ACT_STOP,
    ACT_UP,
    CONF_CHANNELS,
    DOMAIN,
)
from homeassistant.components.inelnet.cover import (
    InelnetCoverEntity,
    async_setup_entry,
    send_command,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def cover_config_entry() -> MockConfigEntry:
    """Config entry for cover tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INELNET test",
        data={CONF_HOST: "192.168.1.67", CONF_CHANNELS: [1, 2]},
        entry_id="test-cover-entry",
        unique_id="192.168.1.67-1,2",
    )


async def test_send_command_payload(hass: HomeAssistant) -> None:
    """Test send_command uses correct URL and payload."""
    post_calls = []

    class MockResponse:
        status = 200

    class AsyncCtx:
        """Async context manager that yields MockResponse."""

        async def __aenter__(self):
            return MockResponse()

        async def __aexit__(self, *args):
            pass

    def capture_post(self, url, *args, data=None, **kwargs):
        post_calls.append((url, data))
        return AsyncCtx()

    class MockSession:
        post = capture_post

    with patch(
        "homeassistant.components.inelnet.cover.async_get_clientsession",
        return_value=MockSession(),
    ):
        result = await send_command(hass, "10.0.0.1", 3, ACT_STOP)

    assert result is True
    assert len(post_calls) == 1
    assert post_calls[0][0] == "http://10.0.0.1/msg.htm"
    assert post_calls[0][1] == "send_ch=3&send_act=144"


async def test_send_command_returns_false_on_network_error(
    hass: HomeAssistant,
) -> None:
    """Test send_command returns False when request raises."""
    failing_ctx = AsyncMock()
    failing_ctx.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
    failing_ctx.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.inelnet.cover.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=failing_ctx)
        mock_session_cls.return_value = mock_session

        result = await send_command(hass, "192.168.1.1", 1, ACT_STOP)

    assert result is False


async def test_cover_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry creates one cover entity per channel."""
    cover_config_entry.runtime_data = MagicMock()
    cover_config_entry.runtime_data.host = "192.168.1.67"
    cover_config_entry.runtime_data.channels = [1, 2]
    added: list = []

    def add_entities(entities):
        added.extend(entities)

    await async_setup_entry(
        hass,
        cover_config_entry,  # type: ignore[arg-type]
        add_entities,
    )

    assert len(added) == 2
    assert all(isinstance(e, InelnetCoverEntity) for e in added)
    assert [e._channel for e in added] == [1, 2]


def test_cover_entity_attributes(cover_config_entry: MockConfigEntry) -> None:
    """Test cover entity has correct attributes and device info."""
    entity = InelnetCoverEntity(cover_config_entry, "192.168.1.67", 1)
    assert entity.unique_id == "test-cover-entry-ch1"
    assert entity.device_info is not None
    identifiers = getattr(
        entity.device_info, "identifiers", entity.device_info.get("identifiers")
    )
    assert identifiers == {(DOMAIN, "test-cover-entry-ch1")}
    name = getattr(entity.device_info, "name", entity.device_info.get("name"))
    assert name == "INELNET Blinds channel 1"
    assert entity.is_closed is None


async def test_cover_open_sends_up_command(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_open_cover calls send_command with ACT_UP."""
    entity = InelnetCoverEntity(cover_config_entry, "192.168.1.67", 1)
    entity.hass = hass
    with patch(
        "homeassistant.components.inelnet.cover.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await entity.async_open_cover()
    mock_send.assert_called_once_with(hass, "192.168.1.67", 1, ACT_UP)


async def test_cover_close_sends_down_command(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_close_cover calls send_command with ACT_DOWN."""
    entity = InelnetCoverEntity(cover_config_entry, "192.168.1.67", 1)
    entity.hass = hass
    with patch(
        "homeassistant.components.inelnet.cover.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await entity.async_close_cover()
    mock_send.assert_called_once_with(hass, "192.168.1.67", 1, ACT_DOWN)


async def test_cover_stop_sends_stop_command(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_stop_cover calls send_command with ACT_STOP."""
    entity = InelnetCoverEntity(cover_config_entry, "192.168.1.67", 1)
    entity.hass = hass
    with patch(
        "homeassistant.components.inelnet.cover.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await entity.async_stop_cover()
    mock_send.assert_called_once_with(hass, "192.168.1.67", 1, ACT_STOP)
