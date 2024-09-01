"""Tests for the Bluesound Media Player platform."""

from pyblu import Player

from homeassistant.core import HomeAssistant


async def test_pause(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player pause."""
    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.pause.assert_called_once()


async def test_play(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player play."""
    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.play.assert_called_once()


async def test_volume_set(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player volume set."""
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": "media_player.player_name", "volume_level": 0.5},
        blocking=True,
    )

    player.volume.assert_called_once_with(50)


async def test_volume_mute(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player volume mute."""
    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": "media_player.player_name", "is_volume_muted": True},
        blocking=True,
    )

    player.volume.assert_called_once_with(mute=True)


async def test_volume_up(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player volume up."""
    await hass.services.async_call(
        "media_player",
        "volume_up",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.volume.assert_called_once_with(11)


async def test_volume_down(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player volume down."""
    await hass.services.async_call(
        "media_player",
        "volume_down",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.volume.assert_called_once_with(9)
