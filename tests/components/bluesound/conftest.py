"""Common fixtures for the Bluesound tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyblu import Status, SyncStatus
import pytest

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

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
        state="playing",
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
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bluesound.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mocked config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.2",
            CONF_PORT: 11000,
        },
        unique_id="00:11:22:33:44:55-11000",
    )
    mock_entry.add_to_hass(hass)

    return mock_entry


@pytest.fixture
def mock_player(status: Status) -> Generator[AsyncMock]:
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
        player.status.return_value = status
        player.sync_status.return_value = SyncStatus(
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
        yield player
