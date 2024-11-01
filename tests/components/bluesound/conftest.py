"""Common fixtures for the Bluesound tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
import ipaddress
from typing import Any
from unittest.mock import AsyncMock, patch

from pyblu import Input, Player, Preset, Status, SyncStatus
import pytest

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .utils import LongPollingMock

from tests.common import MockConfigEntry


@dataclass
class PlayerMockData:
    """Container for player mock data."""

    host: str
    player: AsyncMock
    status_long_polling_mock: LongPollingMock[Status]
    sync_status_long_polling_mock: LongPollingMock[SyncStatus]

    @staticmethod
    async def generate(host: str) -> "PlayerMockData":
        """Generate player mock data."""
        host_ip = ipaddress.ip_address(host)
        assert host_ip.version == 4
        mac_parts = [0xFF, 0xFF, *host_ip.packed]
        mac = ":".join(f"{x:02X}" for x in mac_parts)

        player_name = f"player-name{host.replace('.', '')}"

        player = await AsyncMock(spec=Player)()
        player.__aenter__.return_value = player

        status_long_polling_mock = LongPollingMock(
            Status(
                etag="etag",
                input_id=None,
                service=None,
                state="play",
                shuffle=False,
                album="album",
                artist="artist",
                name="song",
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
        )

        sync_status_long_polling_mock = LongPollingMock(
            SyncStatus(
                etag="etag",
                id=f"{host}:11000",
                mac=mac,
                name=player_name,
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
        )

        player.status.side_effect = status_long_polling_mock.side_effect()
        player.sync_status.side_effect = sync_status_long_polling_mock.side_effect()

        player.inputs = AsyncMock(
            return_value=[
                Input("1", "input1", "image1", "url1"),
                Input("2", "input2", "image2", "url2"),
            ]
        )
        player.presets = AsyncMock(
            return_value=[
                Preset("preset1", "1", "url1", "image1", None),
                Preset("preset2", "2", "url2", "image2", None),
            ]
        )

        return PlayerMockData(
            host, player, status_long_polling_mock, sync_status_long_polling_mock
        )


@dataclass
class PlayerMocks:
    """Container for mocks."""

    player_data: PlayerMockData
    player_data_secondary: PlayerMockData
    player_data_for_already_configured: PlayerMockData


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
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 11000,
        },
        unique_id="ff:ff:01:01:01:01-11000",
    )


@pytest.fixture
def config_entry_secondary() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "2.2.2.2",
            CONF_PORT: 11000,
        },
        unique_id="ff:ff:02:02:02:02-11000",
    )


@pytest.fixture
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, player_mocks: PlayerMocks
) -> None:
    """Set up the platform."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def setup_config_entry_secondary(
    hass: HomeAssistant,
    config_entry_secondary: MockConfigEntry,
    player_mocks: PlayerMocks,
) -> None:
    """Set up the platform."""
    config_entry_secondary.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_secondary.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def player_mocks() -> AsyncGenerator[PlayerMocks]:
    """Mock the player."""
    player_mocks = PlayerMocks(
        player_data=await PlayerMockData.generate("1.1.1.1"),
        player_data_secondary=await PlayerMockData.generate("2.2.2.2"),
        player_data_for_already_configured=await PlayerMockData.generate("1.1.1.2"),
    )

    # to simulate a player that is already configured
    player_mocks.player_data_for_already_configured.sync_status_long_polling_mock.get().mac = player_mocks.player_data.sync_status_long_polling_mock.get().mac

    def select_player(*args: Any, **kwargs: Any) -> AsyncMock:
        match args[0]:
            case "1.1.1.1":
                return player_mocks.player_data.player
            case "2.2.2.2":
                return player_mocks.player_data_secondary.player
            case "1.1.1.2":
                return player_mocks.player_data_for_already_configured.player
            case _:
                raise ValueError("Invalid player")

    with (
        patch(
            "homeassistant.components.bluesound.Player", autospec=True
        ) as mock_player,
        patch(
            "homeassistant.components.bluesound.config_flow.Player",
            new=mock_player,
        ),
    ):
        mock_player.side_effect = select_player

        yield player_mocks
