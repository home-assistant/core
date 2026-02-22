"""Tests for INELNET Blinds button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.inelnet.button import InelnetButtonEntity
from homeassistant.components.inelnet.const import (
    ACT_DOWN_SHORT,
    ACT_PROGRAM,
    ACT_UP_SHORT,
    CONF_CHANNELS,
    DOMAIN,
)
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
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        host="192.168.1.67",
        channel=2,
        unique_id_suffix="short_up",
        action_code=ACT_UP_SHORT,
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


async def test_button_press_sends_command(
    hass: HomeAssistant,
    button_config_entry: MockConfigEntry,
) -> None:
    """Test async_press calls send_command with correct action code."""
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        host="192.168.1.67",
        channel=1,
        unique_id_suffix="program",
        action_code=ACT_PROGRAM,
        translation_key="program",
    )
    entity.hass = hass
    with patch(
        "homeassistant.components.inelnet.button.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await entity.async_press()
    mock_send.assert_called_once_with(hass, "192.168.1.67", 1, ACT_PROGRAM)


async def test_button_short_down_sends_correct_code(
    hass: HomeAssistant,
    button_config_entry: MockConfigEntry,
) -> None:
    """Test Short move down button sends ACT_DOWN_SHORT."""
    entity = InelnetButtonEntity(
        entry=button_config_entry,
        host="10.0.0.1",
        channel=3,
        unique_id_suffix="short_down",
        action_code=ACT_DOWN_SHORT,
        translation_key="short_down",
    )
    entity.hass = hass
    with patch(
        "homeassistant.components.inelnet.button.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await entity.async_press()
    mock_send.assert_called_once_with(hass, "10.0.0.1", 3, ACT_DOWN_SHORT)
