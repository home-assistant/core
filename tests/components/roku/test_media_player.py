"""Tests for the Roku Media Player platform."""
from asynctest import patch

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.roku import setup_integration

MAIN_ENTITY_ID = f"{MP_DOMAIN}.something"


async def test_main_services(hass: HomeAssistantType) -> None:
    """Test the different media player services."""
    await setup_integration(hass)

    with patch("roku.Roku.poweroff") as remote_mock:
        await async_turn_off(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with()

    with patch("roku.Roku.poweron") as remote_mock:
        await async_turn_on(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with()

    with patch("roku.Roku.play") as remote_mock:
        await async_media_pause(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with()

    with patch("roku.Roku.play") as remote_mock:
        await async_media_play(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with()

    with patch("roku.Roku.launch") as tune_mock:
        await async_play_media(hass, "channel", 312, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        tune_mock.assert_called_once_with("312")
