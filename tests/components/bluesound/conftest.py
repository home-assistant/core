"""Common fixtures for the Bluesound tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pyblu import Player, Status, SyncStatus
import pytest

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .utils import ValueStore

from tests.common import MockConfigEntry


@pytest.fixture
def sync_status() -> SyncStatus:
    """Return a sync status object."""
    return SyncStatus(
        etag="etag",
        id="1.1.1.1:11000",
        mac="00:11:22:33:44:55",
        name="player-name",
        image="invalid_url",
        initialized=True,
        brand="brand",
        model="model",
        model_name="model-name",
        volume_db=0.5,
        volume=50,
        group=None,
        master=None,
        slaves=None,
        zone=None,
        zone_master=None,
        zone_slave=None,
        mute_volume_db=None,
        mute_volume=None,
    )


@pytest.fixture
def status() -> Status:
    """Return a status object."""
    return Status(
        etag="etag",
        input_id=None,
        service=None,
        state="play",
        shuffle=False,
        album=None,
        artist=None,
        name=None,
        image=None,
        volume=10,
        volume_db=22.3,
        mute=False,
        mute_volume=None,
        mute_volume_db=None,
        seconds=2,
        total_seconds=123.1,
        can_seek=False,
        sleep=0,
        group_name=None,
        group_volume=None,
        indexing=False,
        stream_url=None,
    )


@pytest.fixture
def status_store(hass: HomeAssistant, status: Status) -> ValueStore[Status]:
    """Return a status store."""
    return ValueStore(status)


@pytest.fixture
def sync_status_store(
    hass: HomeAssistant, sync_status: SyncStatus
) -> ValueStore[SyncStatus]:
    """Return a sync status store."""
    return ValueStore(sync_status)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bluesound.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.2",
            CONF_PORT: 11000,
        },
        unique_id="00:11:22:33:44:55-11000",
    )


@pytest.fixture
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: Player
) -> None:
    """Set up the platform."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def player(
    status_store: ValueStore[Status], sync_status_store: ValueStore[SyncStatus]
) -> Generator[AsyncMock, None, None]:
    """Mock the player."""
    with (
        patch(
            "homeassistant.components.bluesound.Player", autospec=True
        ) as mock_player,
        patch(
            "homeassistant.components.bluesound.config_flow.Player",
            new=mock_player,
        ),
    ):
        player = mock_player.return_value
        player.__aenter__.return_value = player

        player.status.side_effect = status_store.long_polling_mock()
        player.sync_status.side_effect = sync_status_store.long_polling_mock()

        yield player
