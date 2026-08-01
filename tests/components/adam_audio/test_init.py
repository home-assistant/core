"""Tests for ADAM Audio integration __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.adam_audio import _async_reload_entry
from homeassistant.components.adam_audio.const import (
    CONF_DESCRIPTION,
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_DESCRIPTION,
    MOCK_DEVICE_NAME,
    MOCK_HOST,
    MOCK_PORT,
    MOCK_SERIAL,
)

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test setup failure when device is unreachable."""
    mock_client.async_setup = AsyncMock(return_value=False)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test successful unload of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_poll_change_notifies_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test that state changes picked up by polling reach entity states.

    Regression test: the client mutates its state object in place, so the
    coordinator must snapshot it per poll or always_update=False suppresses
    all listener notifications and knob/app changes never reach HA.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("switch.left_speaker_mute").state == "off"

    # Simulate a change made on the physical device (mutated in place, as
    # the real client does), then a poll cycle.
    mock_client.state.mute = True
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("switch.left_speaker_mute").state == "on"


async def test_group_entities_survive_reload(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test group entities are recreated when their owning entry reloads.

    Regression test: the group_*_added flags were never reset on unload, so
    any reload (e.g. after an options update) removed the group entities
    until Home Assistant was restarted.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("switch.all_speakers_mute") is not None

        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.all_speakers_mute") is not None
    assert hass.states.get("number.all_speakers_bass") is not None
    assert hass.states.get("select.all_speakers_voicing") is not None


async def test_async_reload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test _async_reload_entry triggers config entry reload."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as mock_reload:
        await _async_reload_entry(hass, mock_config_entry)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_coordinator_update_failure(
    hass: HomeAssistant, mock_config_entry, mock_client: MagicMock
) -> None:
    """Test coordinator raises UpdateFailed once the client reports unavailable.

    Poll-failure debouncing lives in AdamAudioClient (see test_client.py); the
    coordinator's job is just to trust `client.available` after the poll
    runs, so here we simulate the debounce threshold already being exceeded.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_client.async_fetch_state = AsyncMock(return_value=False)
    mock_client.available = False

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False


async def test_migrates_stale_hardware_name_unique_id(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test an entry's unique_id is migrated from hardware name to serial.

    Regression test: versions up to 0.3.x set the config entry's unique_id
    to the hardware name.  Without migrating it, a later zeroconf
    rediscovery of the same speaker computes a serial-based unique_id,
    _abort_if_unique_id_configured doesn't recognize it as configured, and a
    duplicate entry gets created whose entities collide with the original's.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DESCRIPTION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
            CONF_DESCRIPTION: MOCK_DESCRIPTION,
            CONF_SERIAL: MOCK_SERIAL,
        },
        source="user",
        unique_id=MOCK_DEVICE_NAME,  # stale, pre-serial-migration unique_id
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == MOCK_SERIAL


async def test_does_not_migrate_unique_id_onto_another_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the unique_id migration refuses to collide with another entry.

    If a duplicate entry was already created before this migration existed,
    both entries target the same serial. Migrating the second one anyway
    would silently mask the duplicate; instead it should be left alone (and
    the duplicate resolved manually by the user).
    """
    # Registered (unique_id=MOCK_SERIAL) but deliberately not set up: only
    # its presence in the entry registry matters for the collision check.
    mock_config_entry.add_to_hass(hass)

    duplicate = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DESCRIPTION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
            CONF_DESCRIPTION: MOCK_DESCRIPTION,
            CONF_SERIAL: MOCK_SERIAL,
        },
        source="user",
        unique_id=MOCK_DEVICE_NAME,  # stale, would collide once migrated
    )
    duplicate.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(duplicate.entry_id)
        await hass.async_block_till_done()

    assert duplicate.state is ConfigEntryState.LOADED
    assert duplicate.unique_id == MOCK_DEVICE_NAME  # left untouched

    await hass.config_entries.async_unload(duplicate.entry_id)
    await hass.async_block_till_done()


async def test_unique_id_migration_is_noop_when_already_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the migration doesn't touch an entry whose unique_id is current.

    mock_config_entry is already unique_id=MOCK_SERIAL; setup should not
    issue a redundant async_update_entry call.
    """
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
            return_value=mock_client,
        ),
        patch.object(
            hass.config_entries,
            "async_update_entry",
            wraps=hass.config_entries.async_update_entry,
        ) as mock_update_entry,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.unique_id == MOCK_SERIAL
    mock_update_entry.assert_not_called()


async def test_no_unique_id_migration_without_serial(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test the migration is skipped when the device has no serial yet.

    Older firmware (or a device that hasn't reported a serial over OCA yet)
    leaves device_serial empty; there is nothing to migrate to in that case.
    """
    mock_client.serial = ""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DESCRIPTION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
            CONF_DESCRIPTION: MOCK_DESCRIPTION,
            CONF_SERIAL: "",
        },
        source="user",
        unique_id=MOCK_DEVICE_NAME,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
