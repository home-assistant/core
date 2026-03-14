"""Tests for INELNET Blinds button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.inelnet.button import (
    InelnetButtonEntity,
    async_setup_entry,
)
from homeassistant.components.inelnet.const import CONF_CHANNELS, DOMAIN, Action
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def button_config_entry() -> MockConfigEntry:
    """Config entry for button tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INELNET test",
        data={CONF_HOST: "192.168.1.67", CONF_CHANNELS: [1, 2]},
        entry_id="test-button-entry",
        unique_id="192.168.1.67-1,2",
    )


def test_button_entity_attributes(button_config_entry: MockConfigEntry) -> None:
    """Test button entity has correct unique_id, translation key and device info."""
    mock_client = MagicMock()
    mock_client.channel = 2
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        client=mock_client,
        unique_id_suffix="short_up",
        action=Action.UP_SHORT,
        translation_key="short_up",
    )
    assert entity.unique_id == "test-button-entry-ch2-short_up"
    assert entity.translation_key == "short_up"
    assert entity.device_info is not None
    identifiers = getattr(
        entity.device_info, "identifiers", entity.device_info.get("identifiers")
    )
    assert identifiers == {(DOMAIN, "test-button-entry-ch2")}
    assert entity.entity_registry_enabled_default is False


async def test_button_press_calls_client_send_command(
    hass: HomeAssistant,
    button_config_entry: MockConfigEntry,
) -> None:
    """Test async_press calls client.send_command with action and session."""
    mock_client = MagicMock()
    mock_client.channel = 1
    mock_client.send_command = AsyncMock(return_value=True)
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        client=mock_client,
        unique_id_suffix="program",
        action=Action.PROGRAM,
        translation_key="program",
    )
    entity.hass = hass
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.inelnet.button.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_press()
    mock_client.send_command.assert_called_once_with(
        Action.PROGRAM, session=mock_session
    )


async def test_button_short_down_sends_correct_action(
    hass: HomeAssistant,
    button_config_entry: MockConfigEntry,
) -> None:
    """Test Short move down button sends Action.DOWN_SHORT."""
    mock_client = MagicMock()
    mock_client.channel = 3
    mock_client.send_command = AsyncMock(return_value=True)
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        client=mock_client,
        unique_id_suffix="short_down",
        action=Action.DOWN_SHORT,
        translation_key="short_down",
    )
    entity.hass = hass
    mock_session = MagicMock()
    with patch(
        "homeassistant.components.inelnet.button.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_press()
    mock_client.send_command.assert_called_once_with(
        Action.DOWN_SHORT, session=mock_session
    )


async def test_button_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    button_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry creates three buttons per channel."""
    button_config_entry.runtime_data = MagicMock()
    button_config_entry.runtime_data.clients = {1: MagicMock(), 2: MagicMock()}
    button_config_entry.runtime_data.channels = [1, 2]
    added: list = []

    def add_entities(entities):
        added.extend(entities)

    await async_setup_entry(
        hass,
        button_config_entry,  # type: ignore[arg-type]
        add_entities,
    )

    assert len(added) == 6
    assert all(isinstance(e, InelnetButtonEntity) for e in added)
