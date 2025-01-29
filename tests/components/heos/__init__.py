"""Tests for the Heos component."""

from unittest.mock import AsyncMock

from pyheos import Heos, HeosGroup, HeosOptions, HeosPlayer


class MockHeos(Heos):
    """Defines a mocked HEOS API."""

    def __init__(self, options: HeosOptions) -> None:
        """Initialize the mock."""
        super().__init__(options)
        # Overwrite the methods with async mocks, changing type
        self.add_to_queue: AsyncMock = AsyncMock()
        self.connect: AsyncMock = AsyncMock()
        self.disconnect: AsyncMock = AsyncMock()
        self.get_favorites: AsyncMock = AsyncMock()
        self.get_groups: AsyncMock = AsyncMock()
        self.get_input_sources: AsyncMock = AsyncMock()
        self.get_playlists: AsyncMock = AsyncMock()
        self.get_players: AsyncMock = AsyncMock()
        self.load_players: AsyncMock = AsyncMock()
        self.play_media: AsyncMock = AsyncMock()
        self.play_preset_station: AsyncMock = AsyncMock()
        self.play_url: AsyncMock = AsyncMock()
        self.player_clear_queue: AsyncMock = AsyncMock()
        self.player_get_quick_selects: AsyncMock = AsyncMock()
        self.player_play_next: AsyncMock = AsyncMock()
        self.player_play_previous: AsyncMock = AsyncMock()
        self.player_play_quick_select: AsyncMock = AsyncMock()
        self.player_set_mute: AsyncMock = AsyncMock()
        self.player_set_play_mode: AsyncMock = AsyncMock()
        self.player_set_play_state: AsyncMock = AsyncMock()
        self.player_set_volume: AsyncMock = AsyncMock()
        self.set_group: AsyncMock = AsyncMock()
        self.sign_in: AsyncMock = AsyncMock()
        self.sign_out: AsyncMock = AsyncMock()

    def mock_set_players(self, players: dict[int, HeosPlayer]) -> None:
        """Set the players on the mock instance."""
        for player in players.values():
            player.heos = self
        self._players = players
        self._players_loaded = bool(players)
        self.get_players.return_value = players

    def mock_set_groups(self, groups: dict[int, HeosGroup]) -> None:
        """Set the groups on the mock instance."""
        for group in groups.values():
            group.heos = self
        self._groups = groups
        self._groups_loaded = bool(groups)
        self.get_groups.return_value = groups

    def mock_set_signed_in_username(self, signed_in_username: str | None) -> None:
        """Set the signed in status on the mock instance."""
        self._signed_in_username = signed_in_username
