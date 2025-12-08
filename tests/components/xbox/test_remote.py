"""Test the Xbox remote platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pythonxbox.api.provider.smartglass.models import InputKeyType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def remote_only() -> Generator[None]:
    """Enable only the remote platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.REMOTE],
    ):
        yield


@pytest.mark.usefixtures("xbox_live_client")
async def test_remotes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox remote platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("button", "payload"),
    [
        ("A", InputKeyType.A),
        ("B", InputKeyType.B),
        ("X", InputKeyType.X),
        ("Y", InputKeyType.Y),
        ("Up", InputKeyType.Up),
        ("Down", InputKeyType.Down),
        ("Left", InputKeyType.Left),
        ("Right", InputKeyType.Right),
        ("Menu", InputKeyType.Menu),
        ("View", InputKeyType.View),
        ("Nexus", InputKeyType.Nexus),
    ],
)
async def test_send_button_command(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
    button: str,
    payload: InputKeyType,
) -> None:
    """Test remote send button command."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_COMMAND: button, ATTR_DELAY_SECS: 0},
        target={ATTR_ENTITY_ID: "remote.xone"},
        blocking=True,
    )

    xbox_live_client.smartglass.press_button.assert_called_once_with("HIJKLMN", payload)


@pytest.mark.parametrize(
    ("command", "call_method"),
    [
        ("WakeUp", "wake_up"),
        ("TurnOff", "turn_off"),
        ("Reboot", "reboot"),
        ("Mute", "mute"),
        ("Unmute", "unmute"),
        ("Play", "play"),
        ("Pause", "pause"),
        ("Previous", "previous"),
        ("Next", "next"),
        ("GoHome", "go_home"),
        ("GoBack", "go_back"),
        ("ShowGuideTab", "show_guide_tab"),
        ("ShowGuide", "show_tv_guide"),
    ],
)
async def test_send_command(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
    command: str,
    call_method: str,
) -> None:
    """Test remote send command."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_COMMAND: command, ATTR_DELAY_SECS: 0},
        target={ATTR_ENTITY_ID: "remote.xone"},
        blocking=True,
    )

    call = getattr(xbox_live_client.smartglass, call_method)
    call.assert_called_once_with("HIJKLMN")


async def test_send_text(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test remote send text."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_COMMAND: "Hello", ATTR_DELAY_SECS: 0},
        target={ATTR_ENTITY_ID: "remote.xone"},
        blocking=True,
    )

    xbox_live_client.smartglass.insert_text.assert_called_once_with("HIJKLMN", "Hello")


async def test_turn_on(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test remote turn on."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        target={ATTR_ENTITY_ID: "remote.xone"},
        blocking=True,
    )

    xbox_live_client.smartglass.wake_up.assert_called_once_with("HIJKLMN")


async def test_turn_off(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test remote turn off."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        target={ATTR_ENTITY_ID: "remote.xone"},
        blocking=True,
    )

    xbox_live_client.smartglass.turn_off.assert_called_once_with("HIJKLMN")
