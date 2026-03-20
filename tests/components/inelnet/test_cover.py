"""Tests for INELNET Blinds cover platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.inelnet.const import CONF_CHANNELS, DOMAIN
from homeassistant.components.inelnet.cover import InelnetCoverEntity, async_setup_entry
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
        unique_id="192.168.1.67",
    )


async def test_cover_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry creates one cover entity per channel."""
    cover_config_entry.runtime_data = MagicMock()
    cover_config_entry.runtime_data.clients = {
        1: MagicMock(channel=1),
        2: MagicMock(channel=2),
    }
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
    assert [e._client.channel for e in added] == [1, 2]


def test_cover_entity_attributes(cover_config_entry: MockConfigEntry) -> None:
    """Test cover entity has correct attributes and device info."""
    mock_client = MagicMock()
    mock_client.channel = 1
    entity = InelnetCoverEntity(cover_config_entry, mock_client)
    assert entity.unique_id == "test-cover-entry-ch1"
    assert entity.device_info is not None
    identifiers = getattr(
        entity.device_info, "identifiers", entity.device_info.get("identifiers")
    )
    assert identifiers == {(DOMAIN, "test-cover-entry-ch1")}
    assert (
        getattr(
            entity.device_info,
            "translation_key",
            entity.device_info.get("translation_key"),
        )
        == "channel"
    )
    assert getattr(
        entity.device_info,
        "translation_placeholders",
        entity.device_info.get("translation_placeholders"),
    ) == {"channel": "1"}
    assert entity.is_closed is None


async def test_cover_open_calls_client_up(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_open_cover calls client.up with session."""
    mock_client = MagicMock()
    mock_client.channel = 1
    mock_client.up = AsyncMock(return_value=True)
    entity = InelnetCoverEntity(cover_config_entry, mock_client)
    entity.hass = hass
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.inelnet.cover.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_open_cover()
    mock_client.up.assert_called_once_with(session=mock_session)


async def test_cover_close_calls_client_down(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_close_cover calls client.down with session."""
    mock_client = MagicMock()
    mock_client.channel = 1
    mock_client.down = AsyncMock(return_value=True)
    entity = InelnetCoverEntity(cover_config_entry, mock_client)
    entity.hass = hass
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.inelnet.cover.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_close_cover()
    mock_client.down.assert_called_once_with(session=mock_session)


async def test_cover_stop_calls_client_stop(
    hass: HomeAssistant,
    cover_config_entry: MockConfigEntry,
) -> None:
    """Test async_stop_cover calls client.stop with session."""
    mock_client = MagicMock()
    mock_client.channel = 1
    mock_client.stop = AsyncMock(return_value=True)
    entity = InelnetCoverEntity(cover_config_entry, mock_client)
    entity.hass = hass
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.inelnet.cover.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_stop_cover()
    mock_client.stop.assert_called_once_with(session=mock_session)
